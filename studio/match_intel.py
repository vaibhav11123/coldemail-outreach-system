"""Research Match Intelligence — explainable compatibility, not acceptance probability.

Component weights (initial heuristics, need empirical validation):
  research topic alignment 40%
  publication relevance    25%
  technical skill          20%
  research experience      15%

Funding / recruitment are filters and provenance — they must not silently
reduce research compatibility scores.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from studio.matching import embedding_similarity, overlap_score, tokenize

TOPIC_W = 0.40
PUB_W = 0.25
SKILL_W = 0.20
EXP_W = 0.15


@dataclass
class MatchBreakdown:
    overall: int  # 0–100 research compatibility index (NOT acceptance probability)
    topic: int
    skills: int
    publications: int
    experience: int
    label: str
    why: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    recruitment_note: str = ""
    funding_note: str = ""
    disclaimer: str = (
        "Compatibility is not an acceptance probability. "
        "Recruitment and funding are shown separately."
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _pct(x: float) -> int:
    return max(0, min(100, int(round(100 * x))))


def _label(overall: int) -> str:
    if overall >= 80:
        return "Strong research alignment"
    if overall >= 60:
        return "Promising research alignment"
    if overall >= 40:
        return "Partial research alignment"
    if overall > 0:
        return "Limited research alignment"
    return "Insufficient evidence to score"


def explain_match(
    profile_facts: list[dict[str, Any]],
    opportunity: dict[str, Any],
    publications: list[dict[str, Any]],
) -> MatchBreakdown:
    projects = [f for f in profile_facts if f.get("kind") == "project" and f.get("confirmed")]
    skills = [f for f in profile_facts if f.get("kind") == "skill" and f.get("confirmed")]
    interests = [f for f in profile_facts if f.get("kind") == "interest" and f.get("confirmed")]
    coursework = [f for f in profile_facts if f.get("kind") == "coursework" and f.get("confirmed")]

    student_topic = " ".join(
        f.get("body", "") for f in (interests + projects + coursework)
    )
    student_skills = " ".join(f.get("body", "") for f in skills)
    student_exp = " ".join(f.get("body", "") for f in (projects + coursework))
    lab_text = " ".join(
        filter(
            None,
            [
                opportunity.get("note") or "",
                " ".join(p.get("title") or "" for p in publications),
                " ".join((p.get("abstract") or "")[:400] for p in publications),
            ],
        )
    )

    topic_s, topic_tok = overlap_score(student_topic, lab_text)
    topic_s = max(topic_s, embedding_similarity(student_topic, lab_text) * 0.9)
    skill_s, skill_tok = overlap_score(student_skills, lab_text)
    exp_s, exp_tok = overlap_score(student_exp, lab_text)

    pub_s = 0.0
    best_pub = None
    for pub in publications:
        blob = f"{pub.get('title') or ''} {pub.get('abstract') or ''}"
        s = max(overlap_score(student_topic, blob)[0], embedding_similarity(student_topic, blob))
        if s > pub_s:
            pub_s = s
            best_pub = pub

    overall = TOPIC_W * topic_s + PUB_W * pub_s + SKILL_W * skill_s + EXP_W * exp_s
    why: list[str] = []
    gaps: list[str] = []

    if topic_tok and (interests or projects or coursework):
        src = (interests or projects or coursework)[0]["body"]
        why.append(f"Your interests around “{src[:120]}” overlap with this lab’s sourced research themes.")
    if skill_tok and skills:
        why.append(f"Your skill “{skills[0]['body'][:100]}” appears relevant to the lab description or publications.")
    if best_pub and best_pub.get("title") and pub_s > 0.05:
        why.append(f"Relevant publication: “{best_pub['title'][:140]}”.")
    if projects:
        why.append(f"Confirmed project evidence: “{projects[0]['body'][:120]}”.")
    elif coursework and not projects:
        why.append("No confirmed research project yet — scoring uses coursework and interests.")
        gaps.append("Limited research project evidence; consider confirming a project or lab experience.")
    if not skills:
        gaps.append("Add confirmed technical skills to improve skill alignment.")
    if not publications:
        gaps.append("No sourced publications on file for this researcher in the local catalog.")
    if skill_s < 0.05 and skills:
        gaps.append("Limited overlap between your skills and this lab’s published focus.")

    status = (opportunity.get("status") or "unknown").lower()
    funding = (opportunity.get("funding") or "unknown").lower()
    recruitment_note = {
        "stated-yes": "Confirmed opening (as recorded in catalog).",
        "stated-no": "Not currently recruiting (as recorded).",
        "unknown": "Recruitment unconfirmed — treat as potential supervisor.",
    }.get(status, f"Recruitment status: {status}.")
    funding_note = {
        "stated-yes": "Funding stated yes in catalog (verify independently).",
        "stated-no": "Funding stated no in catalog.",
        "unknown": "Funding unconfirmed.",
    }.get(funding, f"Funding: {funding}.")

    return MatchBreakdown(
        overall=_pct(overall),
        topic=_pct(topic_s),
        skills=_pct(skill_s),
        publications=_pct(pub_s),
        experience=_pct(exp_s),
        label=_label(_pct(overall)),
        why=why[:5],
        gaps=gaps[:4],
        recruitment_note=recruitment_note,
        funding_note=funding_note,
    )


def attach_match_intel_to_shortlist(conn) -> int:
    """Refresh shortlist_item.rank_explanation with MatchBreakdown JSON."""
    facts = [
        dict(r)
        for r in conn.execute(
            "SELECT kind, body, confirmed FROM profile_fact WHERE confirmed = 1"
        )
    ]
    rows = conn.execute("SELECT opportunity_id FROM shortlist_item").fetchall()
    n = 0
    for row in rows:
        oid = row["opportunity_id"]
        opp = conn.execute("SELECT * FROM opportunity WHERE id=?", (oid,)).fetchone()
        if not opp:
            continue
        pubs = [
            dict(p)
            for p in conn.execute(
                "SELECT title, year, url, abstract FROM publication WHERE researcher_id=?",
                (opp["researcher_id"],),
            )
        ]
        breakdown = explain_match(facts, dict(opp), pubs)
        # Keep legacy reasons list under key while adding intel
        payload = {
            "intel": breakdown.to_dict(),
            "reasons": json.loads(
                conn.execute(
                    "SELECT rank_explanation FROM shortlist_item WHERE opportunity_id=?",
                    (oid,),
                ).fetchone()["rank_explanation"]
                or "[]"
            )
            if False
            else [],
        }
        # Prefer fresh reasons from scoring path: store intel + empty reasons; UI uses intel
        payload["reasons"] = [
            {"type": "topic", "applicant": w, "source": "", "url": ""} for w in breakdown.why
        ]
        conn.execute(
            """
            UPDATE shortlist_item
            SET rank_score = ?, rank_explanation = ?
            WHERE opportunity_id = ?
            """,
            (breakdown.overall / 100.0, json.dumps(payload), oid),
            )
        n += 1
    return n
