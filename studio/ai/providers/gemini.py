"""Gemini via AI Studio key — guided setup, not raw jargon on the main card."""

from __future__ import annotations

import requests

from studio.ai.types import (
    ConnectionResult,
    EvidenceBoundRequest,
    ModelInfo,
    ProviderStatus,
    RewriteResult,
)
from studio.secrets_store import delete_secret, get_secret, set_secret

PROVIDER_ID = "gemini"
KEY_SECRET = "ai_gemini_key"


class GeminiProvider:
    id = PROVIDER_ID
    display_name = "Gemini"
    blurb = "Free API tier available through Google AI Studio."
    auth_kind = "guided_key"
    priority = 30
    recommended = False
    advanced = True
    card_title = "Gemini"
    card_subtitle = "Free API tier available"

    def get_status(self) -> ProviderStatus:
        key = get_secret(KEY_SECRET)
        return ProviderStatus(
            id=self.id,
            connected=bool(key),
            label=self.display_name,
            detail="Connected to Google AI Studio."
            if key
            else "We open AI Studio; you create a key once and paste it here.",
            auth_kind="guided_key",
            account_hint=(f"…{key[-4:]}" if key and len(key) >= 4 else ""),
            models=self.list_models() if key else [],
            can_rewrite=bool(key),
            commercial_note="Uses the student's Gemini API quota.",
        )

    def connect_start(self, callback_base: str) -> ConnectionResult:
        return ConnectionResult(
            ok=True,
            provider_id=self.id,
            message="Open Google AI Studio, create a key, then paste it below.",
            redirect_url="https://aistudio.google.com/apikey",
            needs_paste_code=True,
            extra={"paste_kind": "api_key"},
        )

    def connect_finish(self, **kwargs) -> ConnectionResult:
        key = (kwargs.get("api_key") or kwargs.get("code") or "").strip()
        if not key:
            return ConnectionResult(ok=False, provider_id=self.id, message="Paste your AI Studio key.")
        set_secret(KEY_SECRET, key)
        return ConnectionResult(ok=True, provider_id=self.id, message="Gemini connected.")

    def disconnect(self) -> None:
        delete_secret(KEY_SECRET)

    def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="gemini-2.0-flash", label="Gemini 2.0 Flash", free=True)]

    def rewrite(self, request: EvidenceBoundRequest) -> RewriteResult:
        key = get_secret(KEY_SECRET)
        if not key:
            return RewriteResult(ok=False, error="Gemini not connected", provider_id=self.id)
        model = "gemini-2.0-flash"
        prompt = (
            "Rephrase this research outreach letter without adding claims, names, papers, numbers, or URLs.\n\n"
            f"{request.body}"
        )
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={key}"
        )
        try:
            resp = requests.post(
                url,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=60,
            )
        except requests.RequestException as exc:
            return RewriteResult(ok=False, error=str(exc), provider_id=self.id)
        if resp.status_code >= 400:
            return RewriteResult(ok=False, error=f"Gemini HTTP {resp.status_code}", provider_id=self.id)
        data = resp.json()
        try:
            body = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError):
            return RewriteResult(ok=False, error="Unexpected Gemini response", provider_id=self.id)
        return RewriteResult(
            ok=True, subject=request.subject, body=body, provider_id=self.id, model=model
        )
