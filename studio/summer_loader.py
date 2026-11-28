"""Load Summer 2027 research library (or compatible fixture zip) into SQLite."""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

from studio.opportunity_parse import classify_tri_state, parse_deadline, parse_url

HANDS_OFF = {
    "Makoto Yamada",
    "Kenji Doya",
    "Athman Bouguettaya",
    "Malvin Gattinger",
}

SKIP_FILES = {
    "Historical-sends.csv",
    "Historical-quota-audit.csv",
    "Reply-only-history.csv",
    "Considered-not-sent.csv",
    "Untouched-records.csv",
    "READ-ME.txt",
    "research-data.json",
}


def _read_csv(zf: zipfile.ZipFile, name: str) -> list[dict]:
    if name not in zf.namelist():
        return []
    raw = zf.read(name).decode("utf-8-sig", errors="replace")
    return list(csv.DictReader(io.StringIO(raw)))


def _name_key(row: dict) -> str:
    return (
        row.get("Person name")
        or row.get("Full Name")
        or row.get("Name")
        or ""
    ).strip()


def load_summer_zip(conn, zip_path: Path) -> dict:
    """Transactional load. Returns stats. Does not load historical sends."""
    if not zip_path.exists():
        raise FileNotFoundError(str(zip_path))

    stats = {
        "researchers": 0,
        "publications": 0,
        "opportunities": 0,
        "historical_sends_loaded": 0,
        "skipped_files": sorted(SKIP_FILES),
    }

    with zipfile.ZipFile(zip_path) as zf:
        professors = _read_csv(zf, "1-Professor.csv")
        research = _read_csv(zf, "2-Research.csv")
        opportunities = _read_csv(zf, "3-Opportunities.csv")
        funding = _read_csv(zf, "4-Funding.csv")
        eligibility = _read_csv(zf, "5-Eligibility.csv")
        application = _read_csv(zf, "6-Application.csv")
        publications = _read_csv(zf, "Publications.csv")
        # Explicitly ignore historical sends
        if "Historical-sends.csv" in zf.namelist():
            stats["historical_sends_present"] = True

        fund_by = {_name_key(r): r for r in funding}
        elig_by = {_name_key(r): r for r in eligibility}
        app_by = {_name_key(r): r for r in application}
        opp_by = {_name_key(r): r for r in opportunities}
        research_by: dict[str, list] = {}
        for r in research:
            research_by.setdefault(_name_key(r), []).append(r)

        conn.execute("BEGIN IMMEDIATE")
        try:
            # Remove previous bundled rows (keep drafts attached via professor_key on reimport)
            existing = {
                row["professor_key"]: row["id"]
                for row in conn.execute(
                    "SELECT id, professor_key FROM researcher WHERE origin = 'bundled' AND professor_key IS NOT NULL"
                )
            }

            for prow in professors:
                name = _name_key(prow)
                if not name:
                    continue
                email = (prow.get("Institutional Email") or prow.get("Person email") or "").strip()
                university = (prow.get("University") or "").strip()
                orcid = (prow.get("ORCID ID") or "").strip()
                stale = 1 if name in HANDS_OFF else 0
                key = f"summer:{name}|{university}|{email}".lower()

                if key in existing:
                    rid = existing[key]
                    conn.execute(
                        """
                        UPDATE researcher
                        SET display_name = ?, email = ?, stale = ?
                        WHERE id = ?
                        """,
                        (name, email or None, stale, rid),
                    )
                else:
                    cur = conn.execute(
                        """
                        INSERT INTO researcher(display_name, email, origin, stale, professor_key)
                        VALUES (?, ?, 'bundled', ?, ?)
                        """,
                        (name, email or None, stale, key),
                    )
                    rid = cur.lastrowid
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO researcher_id(researcher_id, source, external_id)
                        VALUES (?, 'manual', ?)
                        """,
                        (rid, key),
                    )
                    if orcid:
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO researcher_id(researcher_id, source, external_id)
                            VALUES (?, 'orcid', ?)
                            """,
                            (rid, orcid),
                        )
                    if university:
                        conn.execute(
                            """
                            INSERT INTO affiliation(researcher_id, institution, is_current)
                            VALUES (?, ?, 1)
                            """,
                            (rid, university),
                        )
                stats["researchers"] += 1

                # publications for this person
                for pub in publications:
                    if _name_key(pub) != name:
                        continue
                    title = (pub.get("Title") or pub.get("Paper title") or "").strip()
                    url = (pub.get("URL") or pub.get("Source URL") or pub.get("Paper URL") or "").strip()
                    year_raw = (pub.get("Year") or pub.get("Publication year") or "").strip()
                    if not title or not url.startswith("http"):
                        continue
                    year = None
                    if year_raw.isdigit():
                        year = int(year_raw)
                    # avoid dupes
                    exists = conn.execute(
                        "SELECT id FROM publication WHERE researcher_id = ? AND title = ?",
                        (rid, title),
                    ).fetchone()
                    if exists:
                        continue
                    conn.execute(
                        """
                        INSERT INTO publication(researcher_id, title, year, url, abstract)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (rid, title, year, url, (pub.get("Abstract") or "")[:500] or None),
                    )
                    stats["publications"] += 1

                opp = opp_by.get(name, {})
                fund = fund_by.get(name, {})
                elig = elig_by.get(name, {})
                app = app_by.get(name, {})

                status, status_note = classify_tri_state(
                    opp.get("Opportunity Status (Open / Closed / Rolling / Unknown)")
                    or opp.get("Currently Accepting Applications")
                )
                # Map open/closed vocabulary: stated-yes means applications open
                funding_v, funding_note = classify_tri_state(
                    fund.get("Fully / Partially Funded / Unfunded / Unknown")
                    or fund.get("Funding Availability")
                )
                elig_v, elig_note = classify_tri_state(
                    elig.get("International Applicants Accepted")
                )
                email_inv, email_note = classify_tri_state(
                    app.get("Direct Email Applications Permitted")
                )
                # Never import closed-quota campaign rule as email_invited
                raw_email = str(app.get("Direct Email Applications Permitted") or "")
                if "closed quota" in raw_email.lower() or "no new initial" in raw_email.lower():
                    email_inv, email_note = "unknown", None

                deadline, deadline_note = parse_deadline(opp.get("Application Deadline"))
                apply_url, url_note = parse_url(opp.get("Official Opportunity URL"))
                notes = "; ".join(
                    n
                    for n in [
                        status_note,
                        funding_note,
                        elig_note,
                        email_note,
                        deadline_note,
                        url_note,
                    ]
                    if n
                )

                kind_raw = (opp.get("Opportunity Type (Internship / RA / MS / PhD / Postdoc)") or "").lower()
                if "internship" in kind_raw:
                    kind = "internship"
                elif "visit" in kind_raw:
                    kind = "visit"
                else:
                    kind = "unknown"

                existing_opp = conn.execute(
                    "SELECT id FROM opportunity WHERE researcher_id = ? AND origin = 'bundled'",
                    (rid,),
                ).fetchone()
                if existing_opp:
                    conn.execute(
                        """
                        UPDATE opportunity
                        SET kind=?, status=?, funding=?, eligibility=?, deadline=?,
                            apply_url=?, email_invited=?, checked_at=date('now'), note=?
                        WHERE id=?
                        """,
                        (
                            kind,
                            status,
                            funding_v,
                            elig_v,
                            deadline,
                            apply_url,
                            email_inv,
                            notes or None,
                            existing_opp["id"],
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO opportunity(
                            researcher_id, kind, status, funding, eligibility,
                            deadline, apply_url, email_invited, checked_at, origin, demo, note
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, date('now'), 'bundled', 0, ?)
                        """,
                        (
                            rid,
                            kind,
                            status,
                            funding_v,
                            elig_v,
                            deadline,
                            apply_url,
                            email_inv,
                            notes or None,
                        ),
                    )
                stats["opportunities"] += 1

            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    return stats


def seed_mini_bundled(conn) -> int:
    """Ship a small bundled library when the full Summer zip is unavailable."""
    existing = conn.execute(
        "SELECT COUNT(*) AS c FROM researcher WHERE origin = 'bundled'"
    ).fetchone()["c"]
    if existing:
        return int(existing)
    samples = [
        {
            "name": "Ada Example",
            "email": "ada.example@uni.edu",
            "university": "Example University",
            "status": "unknown",
            "funding": "unknown",
            "eligibility": "unknown",
            "deadline": None,
            "apply_url": "https://example.edu/labs/ada",
            "email_invited": "unknown",
            "note": "Unknown for funded international UG summer; general research invitation as described",
            "paper": {
                "title": "Kernel scheduling for mixture-of-experts inference",
                "year": 2024,
                "url": "https://example.edu/papers/ada-1",
                "abstract": "We study expert scheduling to reduce inference overhead on accelerators.",
            },
        },
        {
            "name": "Ben Example",
            "email": "ben.example@uni.edu",
            "university": "Sample Institute",
            "status": "stated-yes",
            "funding": "stated-yes",
            "eligibility": "stated-yes",
            "deadline": "2099-08-01",
            "apply_url": "https://example.edu/labs/ben/apply",
            "email_invited": "stated-yes",
            "note": "Open",
            "paper": {
                "title": "Systems for research internship matching",
                "year": 2023,
                "url": "https://example.edu/papers/ben-1",
                "abstract": "Matching students to research opportunities with evidence.",
            },
        },
    ]
    conn.execute("BEGIN IMMEDIATE")
    try:
        for s in samples:
            key = f"bundled:{s['name']}".lower()
            cur = conn.execute(
                """
                INSERT INTO researcher(display_name, email, origin, stale, professor_key)
                VALUES (?, ?, 'bundled', 0, ?)
                """,
                (s["name"], s["email"], key),
            )
            rid = cur.lastrowid
            conn.execute(
                "INSERT INTO researcher_id(researcher_id, source, external_id) VALUES (?, 'manual', ?)",
                (rid, key),
            )
            conn.execute(
                "INSERT INTO affiliation(researcher_id, institution, is_current) VALUES (?, ?, 1)",
                (rid, s["university"]),
            )
            pcur = conn.execute(
                """
                INSERT INTO publication(researcher_id, title, year, url, abstract)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    rid,
                    s["paper"]["title"],
                    s["paper"]["year"],
                    s["paper"]["url"],
                    s["paper"]["abstract"],
                ),
            )
            conn.execute(
                "INSERT INTO evidence(publication_id, quote, url) VALUES (?, ?, ?)",
                (pcur.lastrowid, s["paper"]["abstract"], s["paper"]["url"]),
            )
            conn.execute(
                """
                INSERT INTO opportunity(
                    researcher_id, kind, status, funding, eligibility, deadline,
                    apply_url, email_invited, checked_at, origin, demo, note
                ) VALUES (?, 'internship', ?, ?, ?, ?, ?, ?, date('now'), 'bundled', 0, ?)
                """,
                (
                    rid,
                    s["status"],
                    s["funding"],
                    s["eligibility"],
                    s["deadline"],
                    s["apply_url"],
                    s["email_invited"],
                    s["note"],
                ),
            )
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    return len(samples)
