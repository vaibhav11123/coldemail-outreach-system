"""Research-connection ranking with cited reasons."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from typing import Any

# Legacy keys kept for older reason types; primary scoring uses match_intel weights.
WEIGHTS = {"problem": 0.4, "method": 0.25, "skill": 0.2, "activity": 0.15}

STOP = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "for",
    "on",
    "with",
    "by",
    "from",
    "is",
    "are",
    "as",
    "at",
    "this",
    "that",
    "we",
    "our",
    "their",
}


def tokenize(text: str) -> list[str]:
    return [
        t
        for t in re.findall(r"[a-z0-9]+", (text or "").lower())
        if t not in STOP and len(t) > 2
    ]


def overlap_score(a: str, b: str) -> tuple[float, list[str]]:
    ta, tb = set(tokenize(a)), set(tokenize(b))
    if not ta or not tb:
        return 0.0, []
    inter = sorted(ta & tb)
    # Down-weight ultra-generic single tokens
    generic = {"learning", "deep", "machine", "data", "research", "system", "systems"}
    weighted = 0.0
    kept = []
    for token in inter:
        w = 0.25 if token in generic else 1.0
        weighted += w
        kept.append(token)
    denom = math.sqrt(len(ta) * len(tb))
    return (weighted / denom) if denom else 0.0, kept


def embedding_similarity(a: str, b: str) -> float:
    """Lightweight on-device bag-of-words cosine — not a remote model."""
    ca, cb = Counter(tokenize(a)), Counter(tokenize(b))
    if not ca or not cb:
        return 0.0
    keys = set(ca) | set(cb)
    dot = sum(ca[k] * cb[k] for k in keys)
    na = math.sqrt(sum(v * v for v in ca.values()))
    nb = math.sqrt(sum(v * v for v in cb.values()))
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


def score_opportunity(
    profile_facts: list[dict[str, Any]],
    opportunity: dict[str, Any],
    publications: list[dict[str, Any]],
) -> tuple[float, list[dict[str, str]]]:
    projects = [f for f in profile_facts if f.get("kind") == "project" and f.get("confirmed")]
    skills = [f for f in profile_facts if f.get("kind") == "skill" and f.get("confirmed")]
    interests = [f for f in profile_facts if f.get("kind") == "interest" and f.get("confirmed")]

    project_text = " ".join(f.get("body", "") for f in projects)
    skill_text = " ".join(f.get("body", "") for f in skills)
    interest_text = " ".join(f.get("body", "") for f in interests)
    lab_text = " ".join(
        filter(
            None,
            [
                opportunity.get("note") or "",
                " ".join(p.get("title") or "" for p in publications),
                " ".join(p.get("abstract") or "" for p in publications),
            ],
        )
    )

    reasons: list[dict[str, str]] = []

    p_score, p_tokens = overlap_score(project_text or interest_text, lab_text)
    # embedding pass — only keep if we can cite a real sentence
    emb = embedding_similarity(project_text or interest_text, lab_text)
    if emb > p_score:
        # require a quoteable publication sentence
        cite = None
        for pub in publications:
            if pub.get("url") and (pub.get("abstract") or pub.get("title")):
                cite = pub
                break
        if cite:
            p_score = max(p_score, emb)
            reasons.append(
                {
                    "type": "problem",
                    "applicant": (projects[0]["body"] if projects else (interests[0]["body"] if interests else "")),
                    "source": cite.get("abstract") or cite.get("title") or "",
                    "url": cite.get("url") or "",
                }
            )
        # else drop embedding hit
    elif p_tokens and (projects or interests):
        cite = None
        for pub in publications:
            if pub.get("url") and any(t in (pub.get("title") or "").lower() or t in (pub.get("abstract") or "").lower() for t in p_tokens):
                cite = pub
                break
        if cite:
            reasons.append(
                {
                    "type": "problem",
                    "applicant": (projects[0]["body"] if projects else interests[0]["body"]),
                    "source": cite.get("title") or cite.get("abstract") or "",
                    "url": cite.get("url") or "",
                }
            )
        else:
            p_score = 0.0

    m_score, m_tokens = overlap_score(project_text, lab_text)
    if m_tokens and projects:
        cite = None
        for pub in publications:
            if pub.get("url") and any(t in (pub.get("abstract") or "").lower() for t in m_tokens):
                cite = pub
                break
        if cite:
            reasons.append(
                {
                    "type": "method",
                    "applicant": projects[0]["body"],
                    "source": cite.get("abstract") or cite.get("title") or "",
                    "url": cite.get("url") or "",
                }
            )
        else:
            m_score = 0.0

    s_score, s_tokens = overlap_score(skill_text, lab_text)
    if s_tokens and skills:
        reasons.append(
            {
                "type": "skill",
                "applicant": skills[0]["body"],
                "source": opportunity.get("note") or (publications[0].get("title") if publications else "") or "",
                "url": (publications[0].get("url") if publications else "") or "",
            }
        )
    else:
        s_score = 0.0

    # activity: recent paper
    from datetime import date

    year_now = date.today().year
    a_score = 0.0
    for pub in publications:
        year = pub.get("year")
        if year and year_now - int(year) <= 3 and pub.get("url"):
            a_score = 1.0
            reasons.append(
                {
                    "type": "activity",
                    "applicant": "",
                    "source": pub.get("title") or "",
                    "url": pub.get("url") or "",
                }
            )
            break

    # Drop reasons without a source sentence/url when required
    filtered = []
    for r in reasons:
        if r["type"] == "activity" and r["source"] and r["url"]:
            filtered.append(r)
        elif r["applicant"] and r["source"]:
            filtered.append(r)
    reasons = filtered

    total = (
        WEIGHTS["problem"] * p_score
        + WEIGHTS["method"] * m_score
        + WEIGHTS["skill"] * s_score
        + WEIGHTS["activity"] * a_score
    )
    return total, reasons


def rebuild_shortlist(conn) -> int:
    from studio.match_intel import explain_match

    facts = [
        dict(r)
        for r in conn.execute(
            "SELECT kind, body, confirmed FROM profile_fact WHERE confirmed = 1"
        )
    ]
    opps = conn.execute("SELECT * FROM opportunity").fetchall()
    conn.execute("DELETE FROM shortlist_item")
    count = 0
    for opp in opps:
        pubs = [
            dict(p)
            for p in conn.execute(
                "SELECT title, year, url, abstract FROM publication WHERE researcher_id = ?",
                (opp["researcher_id"],),
            )
        ]
        # Citeable legacy reasons (for draft citations) + Match Intelligence breakdown
        score, reasons = score_opportunity(facts, dict(opp), pubs)
        intel = explain_match(facts, dict(opp), pubs)
        payload = {"reasons": reasons, "intel": intel.to_dict()}
        # Prefer explainable compatibility index when evidence exists
        rank = (intel.overall / 100.0) if intel.overall > 0 else score
        conn.execute(
            """
            INSERT INTO shortlist_item(opportunity_id, rank_score, rank_explanation)
            VALUES (?, ?, ?)
            """,
            (opp["id"], rank, json.dumps(payload)),
        )
        count += 1
    return count
