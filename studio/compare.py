"""Faculty comparison matrix across shortlisted researchers."""

from __future__ import annotations

from typing import Any

from studio.match_intel import explain_match


def comparison_rows(
    conn,
    researcher_ids: list[int],
    profile_facts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rid in researcher_ids[:8]:
        researcher = conn.execute(
            "SELECT * FROM researcher WHERE id=?", (rid,)
        ).fetchone()
        if not researcher:
            continue
        aff = conn.execute(
            "SELECT institution FROM affiliation WHERE researcher_id=? AND is_current=1",
            (rid,),
        ).fetchone()
        opp = conn.execute(
            "SELECT * FROM opportunity WHERE researcher_id=? ORDER BY id DESC LIMIT 1",
            (rid,),
        ).fetchone()
        pubs = [
            dict(p)
            for p in conn.execute(
                "SELECT title, year, url, abstract FROM publication WHERE researcher_id=? ORDER BY year DESC",
                (rid,),
            )
        ]
        intel = None
        if opp:
            intel = explain_match(profile_facts, dict(opp), pubs)
        rows.append(
            {
                "researcher_id": rid,
                "name": researcher["display_name"],
                "email": researcher["email"] or "",
                "institution": (aff["institution"] if aff else "") or "—",
                "opportunity_id": opp["id"] if opp else None,
                "funding": (opp["funding"] if opp else "unknown"),
                "status": (opp["status"] if opp else "unknown"),
                "eligibility": (opp["eligibility"] if opp else "unknown"),
                "paper_title": (pubs[0]["title"] if pubs else ""),
                "paper_year": (pubs[0]["year"] if pubs else None),
                "fit_overall": intel.overall if intel else None,
                "fit_label": intel.label if intel else "Not scored",
                "fit_topic": intel.topic if intel else None,
                "fit_skills": intel.skills if intel else None,
                "why": (intel.why[:2] if intel else []),
                "recruitment_note": (intel.recruitment_note if intel else ""),
                "funding_note": (intel.funding_note if intel else ""),
            }
        )
    return rows
