"""Synthetic demo openings — labeled demo, works offline."""

from __future__ import annotations

from datetime import date, timedelta


DEMO_OPENINGS = [
    {
        "display_name": "Demo Lab Alpha",
        "email": "demo.alpha@example.edu",
        "institution": "Demo University",
        "kind": "internship",
        "status": "stated-yes",
        "funding": "stated-yes",
        "eligibility": "stated-yes",
        "deadline": (date.today() + timedelta(days=45)).isoformat(),
        "apply_url": "https://example.edu/demo/alpha/apply",
        "email_invited": "stated-yes",
        "note": "Synthetic demo: open funded internship accepting international students.",
        "papers": [
            {
                "title": "Scheduling experts for efficient transformer inference",
                "year": 2024,
                "url": "https://example.edu/papers/demo-alpha-1",
                "abstract": "We reduce inference overhead through expert scheduling on accelerators.",
            }
        ],
    },
    {
        "display_name": "Demo Lab Beta",
        "email": "demo.beta@example.edu",
        "institution": "Demo College",
        "kind": "internship",
        "status": "stated-no",
        "funding": "stated-no",
        "eligibility": "unknown",
        "deadline": None,
        "apply_url": "https://example.edu/demo/beta",
        "email_invited": "stated-no",
        "note": "Synthetic demo: closed.",
        "papers": [
            {
                "title": "Closed-world evaluation of retrieval systems",
                "year": 2023,
                "url": "https://example.edu/papers/demo-beta-1",
                "abstract": "Retrieval evaluation under closed assumptions.",
            }
        ],
    },
    {
        "display_name": "Demo Lab Gamma",
        "email": "demo.gamma@example.edu",
        "institution": "Demo Institute",
        "kind": "internship",
        "status": "unknown",
        "funding": "unknown",
        "eligibility": "unknown",
        "deadline": None,
        "apply_url": None,
        "email_invited": "unknown",
        "note": "Synthetic demo: funding unknown.",
        "papers": [
            {
                "title": "Unknown-funding case study for student tools",
                "year": 2022,
                "url": "https://example.edu/papers/demo-gamma-1",
                "abstract": "A paper without a stated opening.",
            }
        ],
    },
    {
        "display_name": "Demo Lab Delta",
        "email": "demo.delta@example.edu",
        "institution": "Demo Polytechnic",
        "kind": "internship",
        "status": "stated-yes",
        "funding": "stated-yes",
        "eligibility": "stated-yes",
        "deadline": (date.today() - timedelta(days=10)).isoformat(),
        "apply_url": "https://example.edu/demo/delta/apply",
        "email_invited": "stated-yes",
        "note": "Synthetic demo: expired deadline.",
        "papers": [
            {
                "title": "Expired call archival methods",
                "year": 2021,
                "url": "https://example.edu/papers/demo-delta-1",
                "abstract": "Archiving past internship calls.",
            }
        ],
    },
]


def seed_demo(conn) -> int:
    """Insert demo researchers/opportunities if none exist."""
    existing = conn.execute(
        "SELECT COUNT(*) AS c FROM opportunity WHERE demo = 1"
    ).fetchone()["c"]
    if existing:
        return int(existing)
    count = 0
    conn.execute("BEGIN IMMEDIATE")
    try:
        for item in DEMO_OPENINGS:
            cur = conn.execute(
                """
                INSERT INTO researcher(display_name, email, origin, stale)
                VALUES (?, ?, 'manual', 0)
                """,
                (item["display_name"], item["email"]),
            )
            rid = cur.lastrowid
            conn.execute(
                """
                INSERT INTO researcher_id(researcher_id, source, external_id)
                VALUES (?, 'manual', ?)
                """,
                (rid, f"demo:{item['display_name']}"),
            )
            conn.execute(
                """
                INSERT INTO affiliation(researcher_id, institution, is_current)
                VALUES (?, ?, 1)
                """,
                (rid, item["institution"]),
            )
            for paper in item["papers"]:
                pcur = conn.execute(
                    """
                    INSERT INTO publication(researcher_id, title, year, url, abstract)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        rid,
                        paper["title"],
                        paper["year"],
                        paper["url"],
                        paper["abstract"],
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO evidence(publication_id, quote, url)
                    VALUES (?, ?, ?)
                    """,
                    (pcur.lastrowid, paper["abstract"], paper["url"]),
                )
            ocur = conn.execute(
                """
                INSERT INTO opportunity(
                    researcher_id, kind, status, funding, eligibility,
                    deadline, apply_url, email_invited, checked_at, origin, demo, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, date('now'), 'demo', 1, ?)
                """,
                (
                    rid,
                    item["kind"],
                    item["status"],
                    item["funding"],
                    item["eligibility"],
                    item["deadline"],
                    item["apply_url"],
                    item["email_invited"],
                    item["note"],
                ),
            )
            conn.execute(
                """
                INSERT INTO evidence(opportunity_id, quote, url)
                VALUES (?, ?, ?)
                """,
                (ocur.lastrowid, item["note"], item["apply_url"]),
            )
            count += 1
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    return count
