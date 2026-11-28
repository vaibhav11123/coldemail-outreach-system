"""Encrypted ResearchCatalog.asdb via SQLCipher (AES page encryption)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import sqlcipher3

from studio.dataset.fingerprint import FingerprintContext, export_id_for
from studio.dataset.records import FACTUAL_FIELDS


ASDB_META_KEY = "catalog_format"
ASDB_FORMAT = "academic-studio-asdb-v1"


def _pragma_key(conn, dek: bytes) -> None:
    if len(dek) != 32:
        raise ValueError("DEK must be 32 bytes")
    conn.execute(f"PRAGMA key = \"x'{dek.hex()}'\"")


def build_asdb(
    path: Path,
    records: list[dict[str, Any]],
    *,
    dek: bytes,
    ctx: FingerprintContext,
    sku: str,
) -> dict[str, Any]:
    """Create a fresh encrypted catalog. Overwrites path if present."""
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlcipher3.connect(str(path))
    try:
        _pragma_key(conn, dek)
        conn.execute("PRAGMA cipher_page_size = 4096")
        conn.execute("PRAGMA kdf_iter = 256000")
        conn.executescript(
            """
            CREATE TABLE meta(
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE faculty(
                export_id TEXT PRIMARY KEY,
                canonical_id TEXT NOT NULL UNIQUE,
                display_name TEXT,
                email TEXT,
                university TEXT,
                status TEXT,
                funding TEXT,
                eligibility TEXT,
                deadline TEXT,
                apply_url TEXT,
                email_invited TEXT,
                note TEXT,
                paper_title TEXT,
                paper_year INTEGER,
                paper_url TEXT,
                paper_abstract TEXT
            );
            CREATE INDEX idx_faculty_name ON faculty(display_name);
            CREATE INDEX idx_faculty_university ON faculty(university);
            CREATE INDEX idx_faculty_email ON faculty(email);
            """
        )
        meta = {
            ASDB_META_KEY: ASDB_FORMAT,
            "sku": sku,
            "customer_id": ctx.customer_id,
            "license_id": ctx.license_id,
            "record_count": str(len(records)),
            "fingerprint_scheme": "hmac-sha256-v1",
        }
        for k, v in meta.items():
            conn.execute("INSERT INTO meta(key, value) VALUES (?, ?)", (k, str(v)))

        for rec in records:
            eid = export_id_for(ctx, rec["canonical_id"])
            conn.execute(
                """
                INSERT INTO faculty(
                    export_id, canonical_id, display_name, email, university,
                    status, funding, eligibility, deadline, apply_url, email_invited,
                    note, paper_title, paper_year, paper_url, paper_abstract
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    eid,
                    rec["canonical_id"],
                    rec.get("display_name"),
                    rec.get("email"),
                    rec.get("university"),
                    rec.get("status"),
                    rec.get("funding"),
                    rec.get("eligibility"),
                    rec.get("deadline"),
                    rec.get("apply_url"),
                    rec.get("email_invited"),
                    rec.get("note"),
                    rec.get("paper_title"),
                    rec.get("paper_year"),
                    rec.get("paper_url"),
                    rec.get("paper_abstract"),
                ),
            )
        conn.commit()
        return {"path": str(path), "record_count": len(records), "meta": meta}
    finally:
        conn.close()


def open_asdb(path: Path, dek: bytes):
    """Open encrypted catalog; caller must close the connection."""
    conn = sqlcipher3.connect(str(path))
    _pragma_key(conn, dek)
    # Verify we can read
    row = conn.execute(
        "SELECT value FROM meta WHERE key = ?", (ASDB_META_KEY,)
    ).fetchone()
    if not row or row[0] != ASDB_FORMAT:
        conn.close()
        raise ValueError("Not a valid Academic Studio .asdb catalog (or wrong key)")
    return conn


def export_rows_controlled(
    conn,
    *,
    limit: int | None = None,
    include_canonical: bool = False,
) -> list[dict[str, Any]]:
    """Controlled export for Protected Dataset — still fingerprinted."""
    cols = ["export_id"] + list(FACTUAL_FIELDS)
    if not include_canonical:
        cols = [c for c in cols if c != "canonical_id"]
    sql = f"SELECT {', '.join(cols)} FROM faculty ORDER BY display_name"
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    cur = conn.execute(sql)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def catalog_meta(conn) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM meta").fetchall()
    return {k: v for k, v in rows}


def asdb_plaintext_forbidden_markers() -> list[str]:
    """Strings packaging scans should never find beside an .asdb delivery."""
    return [
        "PRAGMA key",
        "wrapped_dek_plaintext",
    ]
