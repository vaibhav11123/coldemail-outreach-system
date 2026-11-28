"""Build a typed evidence graph for one application draft."""

from __future__ import annotations

from typing import Any

from studio.drafting.schemas import EvidenceItem
from studio.matching import overlap_score


def build_evidence_graph(
    profile_facts: list[dict[str, Any]],
    publications: list[dict[str, Any]],
    reasons: list[dict[str, Any]],
    opportunity: dict[str, Any] | None = None,
) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    n = 0

    def add(kind: str, statement: str, source: str = "", url: str = "", rel: float = 0.5) -> None:
        nonlocal n
        if not (statement or "").strip():
            return
        n += 1
        items.append(
            EvidenceItem(
                id=f"E{n:02d}",
                statement=statement.strip(),
                source=source or statement.strip(),
                url=url or "",
                kind=kind,  # type: ignore[arg-type]
                verified=True,
                relevance=rel,
                permitted_in_email=kind != "opportunity" or bool(url),
            )
        )

    for f in profile_facts:
        if not f.get("confirmed"):
            continue
        kind_map = {
            "project": "student_project",
            "skill": "student_skill",
            "interest": "student_interest",
            "coursework": "student_coursework",
        }
        k = kind_map.get(f.get("kind") or "")
        if k:
            add(k, f.get("body") or "", source=f.get("body") or "", rel=0.7)

    for pub in publications:
        if not pub.get("url"):
            continue
        title = pub.get("title") or ""
        abstract = (pub.get("abstract") or "")[:400]
        add(
            "faculty_publication",
            f"{title}. {abstract}".strip(),
            source=title,
            url=pub.get("url") or "",
            rel=0.8,
        )

    if opportunity and opportunity.get("note"):
        add(
            "faculty_note",
            opportunity.get("note") or "",
            source=opportunity.get("note") or "",
            url=opportunity.get("apply_url") or "",
            rel=0.6,
        )

    for r in reasons or []:
        if r.get("applicant"):
            add("student_project", r["applicant"], source=r.get("source") or "", url=r.get("url") or "", rel=0.75)
        if r.get("source") and r.get("url"):
            add("faculty_publication", r["source"], source=r["source"], url=r["url"], rel=0.75)

    # Relevance re-score vs concatenated student text
    student = " ".join(
        i.statement for i in items if i.kind.startswith("student_")
    )
    for item in items:
        if item.kind.startswith("faculty_"):
            score, _ = overlap_score(student, item.statement)
            item.relevance = max(item.relevance, score)

    items.sort(key=lambda e: e.relevance, reverse=True)
    # Deduplicate near-identical statements
    seen = set()
    unique: list[EvidenceItem] = []
    for item in items:
        key = item.statement.lower()[:120]
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def select_relevant_evidence(
    graph: list[EvidenceItem],
    *,
    limit: int = 8,
) -> list[EvidenceItem]:
    """Relevance-ranked subset for the composer (not first-project-only)."""
    student = sorted(
        [e for e in graph if e.kind.startswith("student_")],
        key=lambda x: x.relevance,
        reverse=True,
    )
    faculty = sorted(
        [e for e in graph if e.kind.startswith("faculty_")],
        key=lambda x: x.relevance,
        reverse=True,
    )
    picked: list[EvidenceItem] = []
    picked.extend(student[:3])
    picked.extend(faculty[:3])
    for e in sorted(graph, key=lambda x: x.relevance, reverse=True):
        if e not in picked:
            picked.append(e)
        if len(picked) >= limit:
            break
    return picked[:limit]


def evidence_allowlist(items: list[EvidenceItem]) -> list[str]:
    out: list[str] = []
    for e in items:
        out.extend([e.statement, e.source, e.url, e.id])
    return out
