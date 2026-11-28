"""Grok / xAI — investigated; commercial redistribution of browser OAuth not confirmed."""

from __future__ import annotations

from studio.ai.types import (
    ConnectionResult,
    EvidenceBoundRequest,
    ModelInfo,
    ProviderStatus,
    RewriteResult,
)
from studio.secrets_store import delete_secret, get_secret, set_secret

PROVIDER_ID = "grok"
KEY_SECRET = "ai_grok_key"


class GrokProvider:
    id = PROVIDER_ID
    display_name = "Grok"
    blurb = "Under investigation — not offered as one-click yet."
    auth_kind = "unavailable"
    priority = 60
    recommended = False
    card_title = "Grok"
    card_subtitle = "Investigating official authorization"
    advanced = True

    def get_status(self) -> ProviderStatus:
        key = get_secret(KEY_SECRET)
        return ProviderStatus(
            id=self.id,
            connected=bool(key),
            label=self.display_name,
            detail=(
                "API key saved (advanced)."
                if key
                else (
                    "Open-source agents document browser OAuth for some SuperGrok / X Premium+ "
                    "tiers, and xAI's Grok Build docs describe OAuth. We have not confirmed that "
                    "independent commercial apps may redistribute that flow or spend consumer "
                    "subscription quotas. Until then, Grok stays in Advanced as an API key only."
                )
            ),
            auth_kind="unavailable" if not key else "guided_key",
            account_hint=(f"…{key[-4:]}" if key and len(key) >= 4 else ""),
            models=[ModelInfo(id="grok", label="Grok")] if key else [],
            can_rewrite=bool(key),
            commercial_note="Do not claim subscription bridge until xAI permits it in writing.",
        )

    def connect_start(self, callback_base: str) -> ConnectionResult:
        return ConnectionResult(
            ok=False,
            provider_id=self.id,
            message=(
                "Grok one-click connect is not enabled. "
                "If you have an xAI API key, paste it under Advanced settings."
            ),
            redirect_url="https://docs.x.ai/",
            needs_paste_code=True,
            extra={"paste_kind": "api_key"},
        )

    def connect_finish(self, **kwargs) -> ConnectionResult:
        key = (kwargs.get("api_key") or kwargs.get("code") or "").strip()
        if not key:
            return ConnectionResult(ok=False, provider_id=self.id, message="Paste an xAI API key.")
        set_secret(KEY_SECRET, key)
        return ConnectionResult(ok=True, provider_id=self.id, message="Grok API key saved.")

    def disconnect(self) -> None:
        delete_secret(KEY_SECRET)

    def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="grok", label="Grok")]

    def rewrite(self, request: EvidenceBoundRequest) -> RewriteResult:
        if not get_secret(KEY_SECRET):
            return RewriteResult(ok=False, error="Grok not connected", provider_id=self.id)
        return RewriteResult(
            ok=False,
            error="Grok rewrite is reserved until commercial OAuth/API policy is confirmed.",
            provider_id=self.id,
        )
