"""Custom OpenAI-compatible endpoint — advanced settings only."""

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

PROVIDER_ID = "custom"
BASE_SECRET = "ai_custom_base"
KEY_SECRET = "ai_custom_key"
MODEL_SECRET = "ai_custom_model"


class CustomProvider:
    id = PROVIDER_ID
    display_name = "Custom AI provider"
    blurb = "API key or compatible endpoint for advanced users."
    auth_kind = "custom"
    priority = 90
    recommended = False
    card_title = "Custom AI provider"
    card_subtitle = "API key or compatible endpoint"
    advanced = True

    def get_status(self) -> ProviderStatus:
        base = get_secret(BASE_SECRET)
        key = get_secret(KEY_SECRET)
        connected = bool(base)
        return ProviderStatus(
            id=self.id,
            connected=connected,
            label=self.display_name,
            detail=base or "Configure an OpenAI-compatible base URL.",
            auth_kind="custom",
            account_hint=(f"…{key[-4:]}" if key and len(key) >= 4 else base or ""),
            models=self.list_models() if connected else [],
            can_rewrite=bool(base),
        )

    def connect_start(self, callback_base: str) -> ConnectionResult:
        return ConnectionResult(
            ok=True,
            provider_id=self.id,
            message="Enter base URL, optional key, and model.",
            needs_paste_code=True,
            extra={"paste_kind": "custom"},
        )

    def connect_finish(self, **kwargs) -> ConnectionResult:
        base = (kwargs.get("base_url") or "").strip().rstrip("/")
        if not base:
            return ConnectionResult(ok=False, provider_id=self.id, message="Base URL is required.")
        if not (base.startswith("http://") or base.startswith("https://")):
            return ConnectionResult(ok=False, provider_id=self.id, message="Base URL must be http or https.")
        # Block private/loopback/link-local destinations (SSRF)
        from studio.security import resolve_and_validate

        try:
            resolve_and_validate(base)
        except ValueError as exc:
            return ConnectionResult(
                ok=False, provider_id=self.id, message=f"Blocked base URL: {exc}"
            )
        set_secret(BASE_SECRET, base)
        if kwargs.get("api_key"):
            set_secret(KEY_SECRET, kwargs["api_key"].strip())
        if kwargs.get("model"):
            set_secret(MODEL_SECRET, kwargs["model"].strip())
        return ConnectionResult(ok=True, provider_id=self.id, message="Custom provider saved.")

    def disconnect(self) -> None:
        delete_secret(BASE_SECRET)
        delete_secret(KEY_SECRET)
        delete_secret(MODEL_SECRET)

    def list_models(self) -> list[ModelInfo]:
        mid = get_secret(MODEL_SECRET) or "default"
        return [ModelInfo(id=mid, label=mid)]

    def rewrite(self, request: EvidenceBoundRequest) -> RewriteResult:
        base = get_secret(BASE_SECRET)
        if not base:
            return RewriteResult(ok=False, error="Custom provider not configured", provider_id=self.id)
        from studio.security import resolve_and_validate

        try:
            resolve_and_validate(base)
        except ValueError as exc:
            return RewriteResult(ok=False, error=f"Blocked base URL: {exc}", provider_id=self.id)
        key = get_secret(KEY_SECRET)
        model = get_secret(MODEL_SECRET) or "default"
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        try:
            resp = requests.post(
                f"{base}/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "Rephrase only. Never invent facts or URLs."},
                        {"role": "user", "content": request.body},
                    ],
                },
                timeout=60,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            return RewriteResult(ok=False, error=str(exc), provider_id=self.id)
        if resp.status_code >= 400:
            return RewriteResult(ok=False, error=f"Custom HTTP {resp.status_code}", provider_id=self.id)
        data = resp.json()
        try:
            body = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError):
            return RewriteResult(ok=False, error="Unexpected custom response", provider_id=self.id)
        return RewriteResult(
            ok=True, subject=request.subject, body=body, provider_id=self.id, model=model
        )
