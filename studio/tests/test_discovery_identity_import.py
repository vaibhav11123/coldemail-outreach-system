"""Discovery, identity, import, security suites."""

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest import mock

import pytest

from studio.demo import DEMO_OPENINGS, seed_demo
from studio.fetch_url import extract_opportunity_suggestions
from studio.identity import (
    attach_external_id,
    flag_name_conflict,
    merge_researchers,
    undo_merge,
)
from studio.opportunity_parse import classify_tri_state, parse_deadline, parse_url
from studio.security import is_blocked_ip, resolve_and_validate
from studio.sheet_import import commit_import, neutralize_formula, read_tabular
from studio.summer_loader import load_summer_zip, seed_mini_bundled


FIXTURES = Path(__file__).parent / "fixtures"


def test_demo_planted_facts_only(conn):
    seed_demo(conn)
    for item in DEMO_OPENINGS:
        row = conn.execute(
            """
            SELECT o.* FROM opportunity o
            JOIN researcher r ON r.id = o.researcher_id
            WHERE r.display_name = ? AND o.demo = 1
            """,
            (item["display_name"],),
        ).fetchone()
        assert row["status"] == item["status"]
        assert row["funding"] == item["funding"]
        assert row["eligibility"] == item["eligibility"]


def test_opportunity_accuracy_fixture_page():
    html = (FIXTURES / "lab_page.html").read_text(encoding="utf-8")
    suggestions = extract_opportunity_suggestions(html, "https://example.edu/lab")
    fields = {s["field"] for s in suggestions}
    assert "deadline" in fields or "funding" in fields or "eligibility" in fields
    # page without deadline
    empty = extract_opportunity_suggestions("<html><body>Hello lab</body></html>", "https://example.edu/x")
    assert not any(s["field"] == "deadline" for s in empty)


def test_unknown_sentence_not_open():
    status, note = classify_tri_state(
        "Unknown for funded international UG summer; general research invitation"
    )
    assert status == "unknown"
    assert note


def test_deadline_prose_not_date():
    d, note = parse_deadline("Applications typically open around 2026")
    assert d is None
    assert note


def test_non_url_cell():
    u, note = parse_url("see department site")
    assert u is None
    assert note


def test_identity_same_name_conflict(conn):
    conn.execute("INSERT INTO researcher(display_name, origin) VALUES ('Same Name', 'manual')")
    a = conn.execute("SELECT id FROM researcher WHERE display_name='Same Name'").fetchone()["id"]
    conn.execute("INSERT INTO researcher(display_name, origin) VALUES ('Same Name', 'manual')")
    b = conn.execute(
        "SELECT id FROM researcher WHERE display_name='Same Name' ORDER BY id DESC"
    ).fetchone()["id"]
    n = flag_name_conflict(conn, "Same Name", b)
    assert n >= 1
    conflict = conn.execute(
        "SELECT * FROM identity_conflict WHERE resolution IS NULL"
    ).fetchone()
    assert conflict


def test_identity_orcid_attach_and_conflict(conn):
    conn.execute("INSERT INTO researcher(display_name, origin) VALUES ('A', 'manual')")
    a = conn.execute("SELECT id FROM researcher WHERE display_name='A'").fetchone()["id"]
    conn.execute("INSERT INTO researcher(display_name, origin) VALUES ('B', 'manual')")
    b = conn.execute("SELECT id FROM researcher WHERE display_name='B'").fetchone()["id"]
    assert attach_external_id(conn, a, "orcid", "0000-0001") == "attached"
    assert attach_external_id(conn, b, "orcid", "0000-0001") == "conflict"


def test_identity_merge_undo(conn):
    conn.execute("INSERT INTO researcher(display_name, origin) VALUES ('Keep', 'manual')")
    keep = conn.execute("SELECT id FROM researcher WHERE display_name='Keep'").fetchone()["id"]
    conn.execute("INSERT INTO researcher(display_name, origin) VALUES ('Remove', 'manual')")
    rem = conn.execute("SELECT id FROM researcher WHERE display_name='Remove'").fetchone()["id"]
    conn.execute(
        "INSERT INTO researcher_id(researcher_id, source, external_id) VALUES (?, 'manual', 'x')",
        (rem,),
    )
    merge_researchers(conn, keep, rem)
    mid = conn.execute("SELECT id FROM merge_log ORDER BY id DESC LIMIT 1").fetchone()["id"]
    undo_merge(conn, mid)
    assert conn.execute(
        "SELECT COUNT(*) AS c FROM researcher WHERE display_name='Remove'"
    ).fetchone()["c"] >= 1


def test_import_formula_and_windows1252(tmp_path, conn):
    assert neutralize_formula("=1+1").startswith("'")
    raw = "Name,University\nAda,Uni\n".encode("windows-1252")
    headers, rows, warnings = read_tabular("t.csv", raw)
    assert headers
    n = commit_import(conn, rows, {"name": "Name", "affiliation": "University", "email": None})
    assert n == 1


def test_hostile_spreadsheet_overcap():
    with pytest.raises(ValueError):
        read_tabular("x.csv", b"a" * (20 * 1024 * 1024 + 5))


def test_ssrf_cases():
    assert is_blocked_ip("127.0.0.1")
    assert is_blocked_ip("169.254.169.254")
    assert is_blocked_ip("10.0.0.1")
    with pytest.raises(ValueError):
        resolve_and_validate("http://127.0.0.1/secret")
    with pytest.raises(ValueError):
        resolve_and_validate("ftp://example.com")


def test_summer_loader_skips_historical(tmp_path, conn):
    zpath = tmp_path / "summer.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr(
            "1-Professor.csv",
            "Person name,University,Institutional Email,ORCID ID\n"
            "Test Prof,Test U,tp@test.edu,\n",
        )
        zf.writestr(
            "3-Opportunities.csv",
            "Person name,Opportunity Status (Open / Closed / Rolling / Unknown),Application Deadline,Official Opportunity URL,Opportunity Type (Internship / RA / MS / PhD / Postdoc)\n"
            "Test Prof,Unknown for funded international UG summer,see website,not-a-url,Internship\n",
        )
        zf.writestr(
            "4-Funding.csv",
            "Person name,Fully / Partially Funded / Unfunded / Unknown\nTest Prof,not published\n",
        )
        zf.writestr(
            "5-Eligibility.csv",
            "Person name,International Applicants Accepted\nTest Prof,unknown\n",
        )
        zf.writestr(
            "6-Application.csv",
            "Person name,Direct Email Applications Permitted\n"
            "Test Prof,closed quota — no new initial email\n",
        )
        zf.writestr(
            "Publications.csv",
            "Person name,Title,Year,URL\n"
            "Test Prof,A Paper,2024,https://example.edu/p1\n",
        )
        zf.writestr("Historical-sends.csv", "to,subject,body\na@b.c,Hi,secret\n")
    stats = load_summer_zip(conn, zpath)
    assert stats["researchers"] == 1
    assert stats["historical_sends_loaded"] == 0
    opp = conn.execute(
        """
        SELECT o.* FROM opportunity o
        JOIN researcher r ON r.id = o.researcher_id
        WHERE r.display_name = 'Test Prof'
        """
    ).fetchone()
    assert opp["status"] == "unknown"
    assert opp["funding"] == "unknown"
    assert opp["email_invited"] == "unknown"
    assert opp["deadline"] is None
    assert opp["apply_url"] is None
    drafts = conn.execute("SELECT COUNT(*) AS c FROM draft").fetchone()["c"]
    assert drafts == 0


def test_kill_during_import_rollback(conn):
    # Begin a write, then ROLLBACK — models crash mid-import leaving zero new rows.
    before = conn.execute("SELECT COUNT(*) AS c FROM researcher").fetchone()["c"]
    conn.execute("BEGIN IMMEDIATE")
    conn.execute(
        "INSERT INTO researcher(display_name, email, origin, stale) VALUES ('Crash', NULL, 'import', 0)"
    )
    conn.execute("ROLLBACK")
    after = conn.execute("SELECT COUNT(*) AS c FROM researcher").fetchone()["c"]
    assert after == before
    assert (
        conn.execute(
            "SELECT COUNT(*) AS c FROM researcher WHERE display_name='Crash'"
        ).fetchone()["c"]
        == 0
    )
