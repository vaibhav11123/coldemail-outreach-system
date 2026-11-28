"""Evidence-bound rewrite engine. AI output is always untrusted."""

from __future__ import annotations

from studio.ai.registry import get_active_provider
from studio.ai.types import EvidenceBoundRequest, RewriteResult
from studio.drafts import generate_draft, has_uncited_claim


REWRITE_SYSTEM = (
    "You rephrase research outreach letters. "
    "You may only rephrase sentences already present. "
    "Do not add new names, paper titles, numbers, URLs, or claims. "
    "Keep every URL and paper title exactly as given. "
    "Return only the letter body text."
)


def validate_rewrite(
    original: EvidenceBoundRequest,
    new_subject: str,
    new_body: str,
) -> tuple[bool, list[str]]:
    """Return (ok, rejected_claim_notes)."""
    allowed = list(original.evidence_snippets)
    allowed.extend([original.body, original.subject])
    for c in original.citations:
        allowed.extend([c.get("applicant", ""), c.get("source", ""), c.get("url", "")])
    # New body must not introduce uncited claims relative to evidence
    # (exclude original body from allowed so model cannot invent then self-cite)
    evidence_only = list(original.evidence_snippets)
    for c in original.citations:
        evidence_only.extend([c.get("applicant", ""), c.get("source", ""), c.get("url", "")])
    if has_uncited_claim(new_body, evidence_only):
        return False, ["AI added an uncited claim. Deterministic draft kept."]
    # Every URL in new body must appear in evidence or original
    from studio.drafts import has_uncited_claim as _

    if has_uncited_claim(new_body, allowed):
        # double-check with broader allow — still fail if brand-new URL
        import re

        urls = re.findall(r"https?://\S+", new_body)
        allow_text = " ".join(allowed)
        for u in urls:
            if u.rstrip(").,") not in allow_text:
                return False, [f"Unknown URL introduced: {u}"]
    return True, []


def rewrite_draft(
    request: EvidenceBoundRequest,
    *,
    force_deterministic: bool = False,
) -> RewriteResult:
    if force_deterministic:
        return _deterministic(request)

    provider = get_active_provider()
    if provider is None:
        return _deterministic(request)

    status = provider.get_status()
    if not status.connected or not status.can_rewrite:
        result = _deterministic(request)
        result.error = status.detail or "AI not connected; used the built-in draft."
        return result

    try:
        raw = provider.rewrite(request)
    except Exception as exc:  # noqa: BLE001
        result = _deterministic(request)
        result.error = f"AI rewrite failed ({exc}); used the built-in draft."
        result.used_deterministic_fallback = True
        return result

    if not raw.ok:
        result = _deterministic(request)
        result.error = raw.error or "AI rewrite failed; used the built-in draft."
        result.used_deterministic_fallback = True
        return result

    ok, rejected = validate_rewrite(request, raw.subject or request.subject, raw.body)
    if not ok:
        result = _deterministic(request)
        result.rejected_claims = rejected
        result.error = rejected[0] if rejected else "AI output rejected."
        result.used_deterministic_fallback = True
        result.provider_id = raw.provider_id
        return result

    raw.subject = raw.subject or request.subject
    return raw


def _deterministic(request: EvidenceBoundRequest) -> RewriteResult:
    # Prefer keeping the student's current draft text when already present
    if request.body.strip():
        return RewriteResult(
            ok=True,
            subject=request.subject,
            body=request.body,
            provider_id="deterministic",
            model="template",
            used_deterministic_fallback=True,
        )
    # Otherwise build from citations if possible
    facts = []
    for c in request.citations:
        if c.get("applicant"):
            facts.append({"kind": "project", "body": c["applicant"], "confirmed": 1})
    pubs = []
    for c in request.citations:
        if c.get("source") or c.get("url"):
            pubs.append(
                {
                    "title": c.get("source") or "",
                    "url": c.get("url") or "",
                    "abstract": c.get("source") or "",
                }
            )
    try:
        draft = generate_draft(
            request.researcher_name or "Professor",
            request.recipient,
            facts or [{"kind": "project", "body": "Confirmed project", "confirmed": 1}],
            pubs,
            request.citations,
        )
        return RewriteResult(
            ok=True,
            subject=draft["subject"],
            body=draft["body"],
            provider_id="deterministic",
            model="template",
            used_deterministic_fallback=True,
        )
    except ValueError as exc:
        return RewriteResult(ok=False, error=str(exc), used_deterministic_fallback=True)
