"""Identity resolution — never silent-merge on name + affiliation."""

from __future__ import annotations

import json


def find_by_external(conn, source: str, external_id: str):
    return conn.execute(
        """
        SELECT r.* FROM researcher r
        JOIN researcher_id ri ON ri.researcher_id = r.id
        WHERE ri.source = ? AND ri.external_id = ?
        """,
        (source, external_id),
    ).fetchone()


def attach_external_id(conn, researcher_id: int, source: str, external_id: str) -> str:
    """Attach ORCID/OpenAlex id. Conflict if owned by someone else."""
    existing = find_by_external(conn, source, external_id)
    if existing and existing["id"] != researcher_id:
        conn.execute(
            """
            INSERT INTO identity_conflict(left_id, right_id, reason)
            VALUES (?, ?, ?)
            """,
            (researcher_id, existing["id"], f"{source} id already on another researcher"),
        )
        return "conflict"
    conn.execute(
        """
        INSERT OR IGNORE INTO researcher_id(researcher_id, source, external_id)
        VALUES (?, ?, ?)
        """,
        (researcher_id, source, external_id),
    )
    return "attached"


def flag_name_conflict(conn, name: str, exclude_id: int | None = None) -> int:
    rows = conn.execute(
        "SELECT id FROM researcher WHERE lower(display_name) = lower(?)",
        (name,),
    ).fetchall()
    ids = [r["id"] for r in rows if exclude_id is None or r["id"] != exclude_id]
    if len(ids) + (0 if exclude_id is None else 1) < 2:
        return 0
    # create pairwise conflicts with first
    base = exclude_id or ids[0]
    created = 0
    for other in ids:
        if other == base:
            continue
        exists = conn.execute(
            """
            SELECT id FROM identity_conflict
            WHERE resolution IS NULL AND (
                (left_id = ? AND right_id = ?) OR (left_id = ? AND right_id = ?)
            )
            """,
            (base, other, other, base),
        ).fetchone()
        if not exists:
            conn.execute(
                """
                INSERT INTO identity_conflict(left_id, right_id, reason)
                VALUES (?, ?, 'Same display name')
                """,
                (base, other),
            )
            created += 1
    return created


def resolve_conflict(conn, conflict_id: int, resolution: str) -> None:
    row = conn.execute(
        "SELECT * FROM identity_conflict WHERE id = ?", (conflict_id,)
    ).fetchone()
    if not row:
        raise ValueError("Conflict not found")
    if resolution not in {"keep-separate", "attach-id", "merge"}:
        raise ValueError("Invalid resolution")
    if resolution == "merge":
        merge_researchers(conn, row["left_id"], row["right_id"])
    conn.execute(
        "UPDATE identity_conflict SET resolution = ? WHERE id = ?",
        (resolution, conflict_id),
    )


def merge_researchers(conn, keep_id: int, remove_id: int) -> None:
    payload = {
        "removed": dict(conn.execute("SELECT * FROM researcher WHERE id = ?", (remove_id,)).fetchone()),
        "ids": [dict(r) for r in conn.execute("SELECT * FROM researcher_id WHERE researcher_id = ?", (remove_id,))],
    }
    conn.execute(
        "INSERT INTO merge_log(kept_id, removed_id, payload) VALUES (?, ?, ?)",
        (keep_id, remove_id, json.dumps(payload, default=str)),
    )
    for table, col in [
        ("affiliation", "researcher_id"),
        ("publication", "researcher_id"),
        ("opportunity", "researcher_id"),
        ("researcher_id", "researcher_id"),
    ]:
        conn.execute(
            f"UPDATE {table} SET {col} = ? WHERE {col} = ?",
            (keep_id, remove_id),
        )
    conn.execute("DELETE FROM researcher WHERE id = ?", (remove_id,))


def undo_merge(conn, merge_id: int) -> None:
    row = conn.execute("SELECT * FROM merge_log WHERE id = ? AND undone = 0", (merge_id,)).fetchone()
    if not row:
        raise ValueError("Merge not found")
    payload = json.loads(row["payload"])
    removed = payload["removed"]
    cur = conn.execute(
        """
        INSERT INTO researcher(display_name, email, origin, stale, professor_key)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            removed.get("display_name"),
            removed.get("email"),
            removed.get("origin") or "manual",
            removed.get("stale") or 0,
            removed.get("professor_key"),
        ),
    )
    new_id = cur.lastrowid
    for rid in payload.get("ids", []):
        conn.execute(
            """
            INSERT OR IGNORE INTO researcher_id(researcher_id, source, external_id)
            VALUES (?, ?, ?)
            """,
            (new_id, rid["source"], rid["external_id"]),
        )
    conn.execute("UPDATE merge_log SET undone = 1 WHERE id = ?", (merge_id,))


def detach_openalex(conn, researcher_id: int, openalex_id: str) -> None:
    conn.execute(
        """
        DELETE FROM researcher_id
        WHERE researcher_id = ? AND source = 'openalex' AND external_id = ?
        """,
        (researcher_id, openalex_id),
    )
    # Flag drafts quoting those papers — mark publications as needing review via note
    conn.execute(
        """
        UPDATE publication SET abstract = COALESCE(abstract, '') || ' [detached-openalex]'
        WHERE researcher_id = ? AND url LIKE ?
        """,
        (researcher_id, f"%{openalex_id}%"),
    )
