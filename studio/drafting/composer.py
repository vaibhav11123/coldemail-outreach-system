"""Compose applications: strategy → evidence-constrained draft (AI optional)."""

from __future__ import annotations

import json
from typing import Any

from studio.drafting.evidence import build_evidence_graph, select_relevant_evidence
from studio.drafting.fallback import deterministic_compose
from studio.drafting.schemas import StructuredDraft, WritingPreferences
from studio.drafting.strategy import select_strategy


def compose_application(
    *,
    researcher_name: str,
    recipient: str,
    profile_facts: list[dict[str, Any]],
    publications: list[dict[str, Any]],
    reasons: list[dict[str, Any]] | None = None,
    opportunity: dict[str, Any] | None = None,
    prefs: WritingPreferences | None = None,
    prior_contact: bool = False,
    use_ai: bool = True,
) -> dict:
    """Return draft dict compatible with existing approve/send pipeline.

    AI composition is attempted when a provider can return structured JSON;
    otherwise deterministic strategy templates are used. Validation remains
    mandatory before approval.
    """
    prefs = prefs or WritingPreferences()
    graph = build_evidence_graph(
        profile_facts, publications, reasons or [], opportunity=opportunity
    )
    if not graph:
        raise ValueError("No confirmed student or faculty evidence available for drafting")

    # Allow learning-oriented path without a confirmed project
    has_student = any(e.kind.startswith("student_") for e in graph)
    if not has_student:
        raise ValueError(
            "Confirm at least one interest, skill, coursework, or project before drafting"
        )
    has_faculty = any(e.kind.startswith("faculty_") for e in graph)
    if not has_faculty:
        raise ValueError(
            "Need at least one sourced faculty publication or lab note"
        )

    selected = select_relevant_evidence(graph, limit=8)
    strategy = select_strategy(
        selected, prefs=prefs, opportunity=opportunity, prior_contact=prior_contact
    )

    if use_ai:
        ai_draft = _try_structured_ai(
            researcher_name=researcher_name,
            recipient=recipient,
            strategy=strategy,
            evidence=selected,
            prefs=prefs,
        )
        if ai_draft is not None:
            return ai_draft

    return deterministic_compose(
        researcher_name=researcher_name,
        recipient=recipient,
        strategy=strategy,
        evidence=selected,
        prefs=prefs,
    )


def _try_structured_ai(
    *,
    researcher_name: str,
    recipient: str,
    strategy: str,
    evidence: list,
    prefs: WritingPreferences,
) -> dict | None:
    """Ask connected provider for StructuredDraft JSON; validate evidence IDs."""
    try:
        from studio.ai.registry import get_active_provider
    except Exception:
        return None
    provider = get_active_provider()
    if provider is None:
        return None
    status = provider.get_status()
    if not status.connected or not getattr(status, "can_rewrite", False):
        return None

    allowed_ids = {e.id for e in evidence}
    evidence_payload = [
        {"id": e.id, "kind": e.kind, "statement": e.statement, "source": e.source, "url": e.url}
        for e in evidence
    ]
    prompt = (
        "Compose a research outreach email as JSON matching this schema: "
        '{"strategy": str, "subject": str, "sections": [{"role": str, "text": str, "evidence_ids": [str]}]}. '
        "Only assert facts from the evidence list. Every factual sentence must list evidence_ids. "
        "Do not invent publications, skills, GPA, funding, or recruitment claims. "
        "Do not paste raw URLs unless present in evidence. "
        f"Strategy hint: {strategy}. Tone: {prefs.tone}. Length: {prefs.length}. "
        f"Recipient name: {researcher_name}. Evidence: {json.dumps(evidence_payload)}"
    )
    # Prefer provider.rewrite with a synthetic EvidenceBoundRequest if available
    try:
        from studio.ai.types import EvidenceBoundRequest

        req = EvidenceBoundRequest(
            subject="(compose)",
            body=prompt,
            evidence_snippets=[e.statement for e in evidence],
            citations=[
                {"applicant": "", "source": e.source, "url": e.url} for e in evidence if e.url
            ],
        )
        raw = provider.rewrite(req)
        if not raw.ok or not raw.body:
            return None
        data = _extract_json(raw.body)
        if not data:
            return None
        draft = StructuredDraft.model_validate(data)
        for section in draft.sections:
            for eid in section.evidence_ids:
                if eid not in allowed_ids:
                    return None
        body = "\n\n".join(s.text.strip() for s in draft.sections if s.text.strip())
        if not body.startswith("Dear"):
            first = researcher_name.split()[0] if researcher_name else "Professor"
            body = f"Dear {first},\n\n{body}\n"
        import hashlib

        ch = hashlib.sha256(
            f"{recipient}\n{draft.subject[:180]}\n{body}".encode()
        ).hexdigest()
        return {
            "recipient": recipient,
            "subject": draft.subject[:180],
            "body": body,
            "content_hash": ch,
            "citations": [
                {
                    "applicant": e.statement if e.kind.startswith("student_") else "",
                    "source": e.source or e.statement,
                    "url": e.url,
                    "evidence_id": e.id,
                }
                for e in evidence
            ],
            "strategy": draft.strategy,
            "evidence_ids": [e.id for e in evidence],
            "composed_by": "ai_structured",
        }
    except Exception:
        return None


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
