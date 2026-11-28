"""SQLite FTS5 index over faculty catalog (BM25 keyword search)."""

from __future__ import annotations

import re
import sqlite3
from typing import Any


FTS_DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS faculty_fts USING fts5(
    researcher_id UNINDEXED,
    display_name,
    institution,
    note,
    paper_titles,
    paper_abstracts,
    tokenize = 'porter unicode61'
);
"""


def ensure_fts(conn: sqlite3.Connection) -> None:
    conn.executescript(FTS_DDL)


def rebuild_faculty_fts(conn: sqlite3.Connection) -> int:
    ensure_fts(conn)
    conn.execute("DELETE FROM faculty_fts")
    rows = conn.execute(
        """
        SELECT r.id AS rid,
               r.display_name,
               (
                 SELECT institution FROM affiliation a
                 WHERE a.researcher_id = r.id AND a.is_current = 1 LIMIT 1
               ) AS institution,
               (
                 SELECT GROUP_CONCAT(o.note, ' ') FROM opportunity o
                 WHERE o.researcher_id = r.id
               ) AS note,
               (
                 SELECT GROUP_CONCAT(p.title, ' ') FROM publication p
                 WHERE p.researcher_id = r.id
               ) AS paper_titles,
               (
                 SELECT GROUP_CONCAT(p.abstract, ' ') FROM publication p
                 WHERE p.researcher_id = r.id
               ) AS paper_abstracts
        FROM researcher r
        """
    ).fetchall()
    for row in rows:
        conn.execute(
            """
            INSERT INTO faculty_fts(
                researcher_id, display_name, institution, note, paper_titles, paper_abstracts
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                row["rid"],
                row["display_name"] or "",
                row["institution"] or "",
                row["note"] or "",
                row["paper_titles"] or "",
                row["paper_abstracts"] or "",
            ),
        )
    return len(rows)


def _sanitize_fts_query(q: str) -> str:
    """Turn free text into a safe FTS5 OR-of-tokens query."""
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{1,}", q)
    if not tokens:
        return ""
    # Quote each token so operators like AND/OR/- are literal
    return " OR ".join(f'"{t}"' for t in tokens[:24])


def search_faculty_fts(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    ensure_fts(conn)
    fts_q = _sanitize_fts_query(query)
    if not fts_q:
        return []
    # Rebuild if empty (first use after migrate)
    count = conn.execute("SELECT COUNT(*) AS c FROM faculty_fts").fetchone()["c"]
    if count == 0:
        rebuild_faculty_fts(conn)
    rows = conn.execute(
        """
        SELECT researcher_id,
               bm25(faculty_fts) AS bm25,
               snippet(faculty_fts, 1, '<mark>', '</mark>', '…', 12) AS name_snip,
               snippet(faculty_fts, 2, '<mark>', '</mark>', '…', 12) AS inst_snip,
               snippet(faculty_fts, 4, '<mark>', '</mark>', '…', 18) AS paper_snip
        FROM faculty_fts
        WHERE faculty_fts MATCH ?
        ORDER BY bm25(faculty_fts)
        LIMIT ?
        """,
        (fts_q, int(limit)),
    ).fetchall()
    return [dict(r) for r in rows]
