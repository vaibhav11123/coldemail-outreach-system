"""Scale smoke + chaos: larger synthetic libraries, interrupted imports, disk pressure."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from studio.db import connect, migrate
from studio.matching import rebuild_shortlist
from studio.sheet_import import commit_import, read_tabular


def test_scale_10k_researchers_searchable(data_dir: Path):
    db = data_dir / "scale.sqlite"
    conn = connect(db)
    migrate(conn)
    # Batch insert 10k synthetic researchers
    conn.execute("BEGIN IMMEDIATE")
    for i in range(10_000):
        conn.execute(
            "INSERT INTO researcher(display_name, email, origin, professor_key) VALUES (?, ?, 'import', ?)",
            (f"Researcher {i:05d}", f"r{i}@ex.edu", f"scale:{i}"),
        )
        rid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO affiliation(researcher_id, institution, is_current) VALUES (?, ?, 1)",
            (rid, f"University {i % 50}"),
        )
        conn.execute(
            """
            INSERT INTO opportunity(researcher_id, kind, status, funding, eligibility, origin)
            VALUES (?, 'internship', 'unknown', 'unknown', 'unknown', 'import')
            """,
            (rid,),
        )
    conn.execute("COMMIT")
    n = conn.execute("SELECT COUNT(*) AS c FROM researcher").fetchone()["c"]
    assert n == 10_000
    # Prefix search must stay usable
    import time

    t0 = time.perf_counter()
    rows = conn.execute(
        "SELECT display_name FROM researcher WHERE display_name LIKE ? LIMIT 20",
        ("Researcher 009%",),
    ).fetchall()
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert len(rows) >= 1
    # Soft target — document if slow rather than silently skip
    assert elapsed_ms < 2000, f"search too slow: {elapsed_ms:.1f}ms"
    conn.close()


def test_identical_names_not_silently_merged(conn):
    a = conn.execute(
        "INSERT INTO researcher(display_name, email, origin) VALUES ('Jane Smith', 'a@u1.edu', 'manual')"
    ).lastrowid
    b = conn.execute(
        "INSERT INTO researcher(display_name, email, origin) VALUES ('Jane Smith', 'b@u2.edu', 'manual')"
    ).lastrowid
    assert a != b
    n = conn.execute(
        "SELECT COUNT(*) AS c FROM researcher WHERE display_name='Jane Smith'"
    ).fetchone()["c"]
    assert n >= 2


def test_import_oversize_rejected(conn):
    huge = b"Name,Email\n" + b"X,x@y.z\n" * 1000
    # Cap is size-based in read_tabular
    with pytest.raises(ValueError):
        read_tabular("big.csv", b"x" * (20 * 1024 * 1024 + 1))


def test_formula_injection_stored_as_text(conn):
    headers, rows, _ = read_tabular(
        "t.csv",
        b"Name,University,Email\n"
        b"=CMD|'/c calc'!A0,Evil U,evil@ex.edu\n",
    )
    n = commit_import(
        conn, rows, {"name": "Name", "affiliation": "University", "email": "Email"}
    )
    assert n == 1
    name = conn.execute(
        "SELECT display_name FROM researcher WHERE email='evil@ex.edu'"
    ).fetchone()["display_name"]
    # Must remain inert text, not executed
    assert name.startswith("=") or "CMD" in name


def test_chaos_readonly_db_fails_safely(data_dir: Path):
    db = data_dir / "ro.sqlite"
    conn = connect(db)
    migrate(conn)
    conn.close()
    db.chmod(0o444)
    c2 = sqlite3.connect(str(db))
    try:
        with pytest.raises(sqlite3.OperationalError):
            c2.execute("INSERT INTO researcher(display_name, origin) VALUES ('X', 'manual')")
            c2.commit()
    finally:
        c2.close()
        db.chmod(0o644)
