"""Application strategy selection from available evidence + intent."""

from __future__ import annotations

from typing import Any

from studio.drafting.schemas import EvidenceItem, StrategyName, WritingPreferences


def select_strategy(
    evidence: list[EvidenceItem],
    *,
    prefs: WritingPreferences | None = None,
    opportunity: dict[str, Any] | None = None,
    prior_contact: bool = False,
) -> StrategyName:
    prefs = prefs or WritingPreferences()
    if prior_contact:
        return "follow_up"
    if prefs.intent in {"phd", "phd_inquiry"}:
        return "phd_inquiry"
    if prefs.intent in {"collaboration", "remote"}:
        return "collaboration_inquiry"

    has_project = any(e.kind == "student_project" for e in evidence)
    has_course = any(e.kind == "student_coursework" for e in evidence)
    has_skill = any(e.kind == "student_skill" for e in evidence)
    has_pub = any(e.kind == "faculty_publication" for e in evidence)
    status = ((opportunity or {}).get("status") or "").lower()

    if status in {"stated-yes", "open", "accepting"}:
        return "advertised_opening"
    if has_pub and has_project:
        return "publication_led" if prefs.emphasis == "publication" else "technical_contribution"
    if has_project and has_skill:
        return "technical_contribution"
    if has_pub and (has_course or any(e.kind == "student_interest" for e in evidence)):
        return "research_alignment"
    if not has_project and (has_course or has_skill):
        return "learning_oriented"
    return "research_alignment"
