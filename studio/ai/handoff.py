"""Universal external-AI handoff — student uses their own AI client; we never hold sub tokens."""

from __future__ import annotations

from urllib.parse import quote

from studio.ai.engine import REWRITE_SYSTEM, validate_rewrite
from studio.ai.types import EvidenceBoundRequest, RewriteResult

HANDOFF_TARGETS = [
    {"id": "chatgpt", "title": "ChatGPT", "open_url": "https://chatgpt.com/"},
    {"id": "claude", "title": "Claude", "open_url": "https://claude.ai/"},
    {"id": "gemini", "title": "Gemini", "open_url": "https://gemini.google.com/"},
    {"id": "grok", "title": "Grok", "open_url": "https://grok.x.ai/"},
    {"id": "deepseek", "title": "DeepSeek", "open_url": "https://chat.deepseek.com/"},
    {"id": "copilot", "title": "Copilot", "open_url": "https://github.com/copilot"},
]


def build_handoff_prompt(request: EvidenceBoundRequest) -> str:
    """Structured prompt with only confirmed facts + evidence — safe to paste into any AI."""
    evidence_lines = [
        f"- {snip.strip()}" for snip in request.evidence_snippets if snip.strip()
    ]
    cite_lines = []
    for c in request.citations:
        cite_lines.append(
            f"- {c.get('applicant', '')} ← {c.get('source', '')} {c.get('url', '')}".strip()
        )
    evidence_block = "\n".join(evidence_lines) or "- (none listed)"
    cite_block = "\n".join(cite_lines) or "- (none listed)"
    return (
        f"{REWRITE_SYSTEM}\n\n"
        f"Recipient: {request.recipient}\n"
        f"Subject (keep or lightly polish): {request.subject}\n\n"
        f"Confirmed evidence you may use (do not invent beyond this):\n"
        f"{evidence_block}\n\n"
        f"Citations:\n{cite_block}\n\n"
        f"Current letter body:\n"
        f"-----\n{request.body}\n-----\n\n"
        f"Return only the improved letter body. Do not add a subject line or commentary."
    )


def import_handoff_body(
    request: EvidenceBoundRequest,
    imported_body: str,
) -> RewriteResult:
    body = (imported_body or "").strip()
    if not body:
        return RewriteResult(
            ok=False,
            subject=request.subject,
            body=request.body,
            error="Paste the letter body returned by your AI assistant.",
            used_deterministic_fallback=True,
            provider_id="external_handoff",
        )
    ok, notes = validate_rewrite(request, request.subject, body)
    if not ok:
        return RewriteResult(
            ok=False,
            subject=request.subject,
            body=request.body,
            error="; ".join(notes) or "Imported text failed evidence checks.",
            used_deterministic_fallback=True,
            provider_id="external_handoff",
        )
    return RewriteResult(
        ok=True,
        subject=request.subject,
        body=body,
        provider_id="external_handoff",
        model="user-ai-client",
    )


def chatgpt_share_url(prompt: str) -> str:
    return f"https://chatgpt.com/?q={quote(prompt[:1500])}"
