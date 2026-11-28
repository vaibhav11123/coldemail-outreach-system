"""Managed Groq inference — key stays in process env / hosted secrets, never a student paste."""

from __future__ import annotations

import os

import requests

from studio.ai.types import (
    ConnectionResult,
    EvidenceBoundRequest,
    ModelInfo,
    ProviderStatus,
    RewriteResult,
)
from studio.secrets_store import delete_secret, get_secret, set_secret

PROVIDER_ID = "groq"
ENABLED_SECRET = "ai_groq_managed_enabled"
DEFAULT_MODEL = "openai/gpt-oss-20b"
API_URL = "https://api.groq.com/openai/v1/chat/completions"


def _api_key() -> str:
    # Hosted/managed only — never embed in the downloadable client as a shared secret
    return (
        os.environ.get("STUDIO_GROQ_API_KEY")
        or os.environ.get("GROQ_API_KEY")
        or get_secret("ai_groq_managed_key")
        or ""
    )


class GroqManagedProvider:
    id = PROVIDER_ID
    display_name = "Included AI (Groq)"
    blurb = "Ready-to-use rewrite when this build includes managed inference. No AI account required."
    auth_kind = "managed"
    priority = 1
    recommended = True
    advanced = False
    card_title = "Included AI"
    card_subtitle = "Managed Groq — no student account"
    advanced = False  # shown beside Free AI when configured; otherwise explains fallback

    def get_status(self) -> ProviderStatus:
        key = _api_key()
        enabled = get_secret(ENABLED_SECRET) == "1" or bool(
            os.environ.get("STUDIO_GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
        )
        connected = bool(key) and enabled
        if not key:
            detail = (
                "Managed Groq is not configured for this build. "
                "Use Free AI (OpenRouter), Offline AI, or Improve with your AI."
            )
        elif not enabled:
            detail = "Managed Groq key present — enable Included AI to use it within product budgets."
        else:
            detail = "Ready. Usage is billed to the product’s Groq allowance (rate-limited)."
        return ProviderStatus(
            id=self.id,
            connected=connected,
            label=self.display_name,
            detail=detail,
            auth_kind="managed",
            account_hint="managed" if connected else "",
            models=self.list_models() if connected else [],
            can_rewrite=connected,
            commercial_note=(
                "Never pool free accounts. Respect Groq rate limits and model licenses."
            ),
        )

    def connect_start(self, callback_base: str) -> ConnectionResult:
        if not _api_key():
            return ConnectionResult(
                ok=False,
                provider_id=self.id,
                message=(
                    "This build has no managed Groq key. "
                    "Connect Free AI or use Improve with your AI on the draft screen."
                ),
            )
        set_secret(ENABLED_SECRET, "1")
        return ConnectionResult(
            ok=True,
            provider_id=self.id,
            message="Included AI (Groq) enabled for this workspace.",
        )

    def connect_finish(self, **kwargs) -> ConnectionResult:
        return self.connect_start("")

    def disconnect(self) -> None:
        delete_secret(ENABLED_SECRET)

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id=DEFAULT_MODEL, label="GPT-OSS 20B (Groq)", free=True),
            ModelInfo(id="openai/gpt-oss-120b", label="GPT-OSS 120B (Groq)", free=False),
        ]

    def rewrite(self, request: EvidenceBoundRequest) -> RewriteResult:
        key = _api_key()
        if not key:
            return RewriteResult(ok=False, error="Managed Groq not configured.")
        from studio.ai.engine import REWRITE_SYSTEM

        payload = {
            "model": DEFAULT_MODEL,
            "messages": [
                {"role": "system", "content": REWRITE_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"Subject: {request.subject}\n\n{request.body}\n\n"
                        f"Evidence: {'; '.join(request.evidence_snippets)[:2000]}"
                    ),
                },
            ],
            "temperature": 0.2,
            "max_tokens": 1200,
        }
        try:
            resp = requests.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60,
            )
        except requests.RequestException as exc:
            return RewriteResult(ok=False, error=str(exc))
        if resp.status_code == 429:
            return RewriteResult(
                ok=False,
                error="Groq rate limit reached. Try again later or use Free AI / built-in draft.",
            )
        if resp.status_code >= 400:
            return RewriteResult(ok=False, error=f"Groq HTTP {resp.status_code}")
        data = resp.json()
        try:
            body = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError):
            return RewriteResult(ok=False, error="Unexpected Groq response.")
        return RewriteResult(
            ok=True,
            subject=request.subject,
            body=body,
            provider_id=self.id,
            model=DEFAULT_MODEL,
        )
