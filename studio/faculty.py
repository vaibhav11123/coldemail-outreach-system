"""Faculty directory collector — Python fetcher, not the old Ruby scripts."""

from __future__ import annotations

from typing import Any

from studio.fetch_url import extract_people_from_html, fetch_text

# Seed list of schools (URLs may change; failures are expected and named)
SCHOOLS = [
    {
        "id": "mit",
        "name": "Massachusetts Institute of Technology",
        # Role listing moved; /people/faculty-advisors/ is a 404 as of 2026-11.
        "url": "https://www.eecs.mit.edu/role/faculty/",
        "openalex_institution": "I63966007",
    },
    {
        "id": "stanford",
        "name": "Stanford University",
        "url": "https://www.cs.stanford.edu/people/faculty",
        "openalex_institution": "I97018004",
    },
    {
        "id": "berkeley",
        "name": "UC Berkeley",
        "url": "https://www2.eecs.berkeley.edu/Faculty/Lists/faculty.html",
        "openalex_institution": "I95457486",
    },
]


def list_schools() -> list[dict[str, str]]:
    return [{"id": s["id"], "name": s["name"]} for s in SCHOOLS]


def school_by_id(school_id: str) -> dict[str, str] | None:
    for s in SCHOOLS:
        if s["id"] == school_id:
            return s
    return None


def collect_school(school_id: str, openalex_fallback=None) -> dict[str, Any]:
    school = school_by_id(school_id)
    if not school:
        raise ValueError(f"Unknown school: {school_id}")
    people: list[dict[str, str]] = []
    error = None
    try:
        final_url, html = fetch_text(school["url"])
        people = extract_people_from_html(html, final_url)
    except Exception as exc:  # noqa: BLE001
        error = str(exc)
        people = []

    used_openalex = False
    if not people and openalex_fallback is not None:
        try:
            people = openalex_fallback(school.get("openalex_institution"))
            used_openalex = True
            # OpenAlex authors typically lack email
            for p in people:
                p.setdefault("email", "")
        except Exception as exc:  # noqa: BLE001
            error = f"{error + '; ' if error else ''}OpenAlex fallback failed: {exc}"

    return {
        "school": school,
        "people": people,
        "error": error if not people else None,
        "used_openalex": used_openalex,
    }


def import_people(conn, school_id: str, people: list[dict[str, str]]) -> int:
    if not people:
        return 0
    school = school_by_id(school_id)
    institution = school["name"] if school else school_id
    count = 0
    conn.execute("BEGIN IMMEDIATE")
    try:
        for person in people:
            name = (person.get("name") or "").strip()
            email = (person.get("email") or "").strip().lower()
            if not name and not email:
                continue
            existing = None
            if email:
                existing = conn.execute(
                    "SELECT id FROM researcher WHERE lower(email) = ? AND origin = 'faculty'",
                    (email,),
                ).fetchone()
            if existing:
                rid = existing["id"]
                conn.execute(
                    "UPDATE researcher SET display_name = ? WHERE id = ?",
                    (name or email, rid),
                )
            else:
                cur = conn.execute(
                    """
                    INSERT INTO researcher(display_name, email, origin, stale)
                    VALUES (?, ?, 'faculty', 0)
                    """,
                    (name or email, email or None),
                )
                rid = cur.lastrowid
                ext = email or f"faculty:{school_id}:{name}".lower()
                conn.execute(
                    """
                    INSERT OR IGNORE INTO researcher_id(researcher_id, source, external_id)
                    VALUES (?, 'manual', ?)
                    """,
                    (rid, ext),
                )
                conn.execute(
                    """
                    INSERT INTO affiliation(researcher_id, institution, is_current)
                    VALUES (?, ?, 1)
                    """,
                    (rid, institution),
                )
                # Opportunity with all unknowns
                conn.execute(
                    """
                    INSERT INTO opportunity(
                        researcher_id, kind, status, funding, eligibility,
                        deadline, apply_url, email_invited, checked_at, origin, demo, note
                    ) VALUES (?, 'unknown', 'unknown', 'unknown', 'unknown',
                              NULL, NULL, 'unknown', date('now'), 'faculty', 0, ?)
                    """,
                    (rid, f"Imported from {institution} directory"),
                )
            count += 1
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return count
