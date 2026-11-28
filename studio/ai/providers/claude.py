"""Claude — API key path + Claude Platform OAuth note (beta, not consumer Pro/Max)."""

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

PROVIDER_ID = "claude"
KEY_SECRET = "ai_claude_key"


class ClaudeProvider:
    id = PROVIDER_ID
    display_name = "Claude"
    blurb = "Connect your API account (not Claude Pro/Max chat)."
    auth_kind = "guided_key"
    priority = 50
    recommended = False
    card_title = "Claude"
    card_subtitle = "Connect your API account"
    advanced = True

    def get_status(self) -> ProviderStatus:
        key = get_secret(KEY_SECRET)
        return ProviderStatus(
            id=self.id,
            connected=bool(key),
            label=self.display_name,
            detail=(
                "API key saved."
                if key
                else (
                    "Paste a console.anthropic.com API key. "
                    "Claude Platform OAuth exists for organizations (beta) and does not "
                    "spend Claude Pro or Max subscription allowance."
                )
            ),
            auth_kind="guided_key",
            account_hint=(f"…{key[-4:]}" if key and len(key) >= 4 else ""),
            models=[ModelInfo(id="claude-sonnet-4-5", label="Claude Sonnet")] if key else [],
            can_rewrite=bool(key),
            commercial_note="Consumer Claude subscriptions cannot be used through Platform OAuth.",
        )

    def connect_start(self, callback_base: str) -> ConnectionResult:
        return ConnectionResult(
            ok=True,
            provider_id=self.id,
            message="Open Anthropic Console, create a key, paste it below.",
            redirect_url="https://console.anthropic.com/",
            needs_paste_code=True,
            extra={"paste_kind": "api_key"},
        )

    def connect_finish(self, **kwargs) -> ConnectionResult:
        key = (kwargs.get("api_key") or kwargs.get("code") or "").strip()
        if not key:
            return ConnectionResult(ok=False, provider_id=self.id, message="Paste your Claude API key.")
        set_secret(KEY_SECRET, key)
        return ConnectionResult(ok=True, provider_id=self.id, message="Claude API connected.")

    def disconnect(self) -> None:
        delete_secret(KEY_SECRET)

    def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="claude-sonnet-4-5", label="Claude Sonnet")]

    def rewrite(self, request: EvidenceBoundRequest) -> RewriteResult:
        key = get_secret(KEY_SECRET)
        if not key:
            return RewriteResult(ok=False, error="Claude not connected", provider_id=self.id)
        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-5",
                    "max_tokens": 1024,
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                "Rephrase this research letter. Do not add claims, names, papers, "
                                f"numbers, or URLs.\n\n{request.body}"
                            ),
                        }
                    ],
                },
                timeout=60,
            )
        except requests.RequestException as exc:
            return RewriteResult(ok=False, error=str(exc), provider_id=self.id)
        if resp.status_code >= 400:
            return RewriteResult(ok=False, error=f"Claude HTTP {resp.status_code}", provider_id=self.id)
        data = resp.json()
        try:
            body = data["content"][0]["text"].strip()
        except (KeyError, IndexError, TypeError):
            return RewriteResult(ok=False, error="Unexpected Claude response", provider_id=self.id)
        return RewriteResult(
            ok=True,
            subject=request.subject,
            body=body,
            provider_id=self.id,
            model="claude-sonnet-4-5",
        )
