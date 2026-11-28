"""ChatGPT Sign-in — OAuth PKCE scaffold; commercial eligibility required for paid apps."""

from __future__ import annotations

import secrets

from studio.ai.types import (
    ConnectionResult,
    EvidenceBoundRequest,
    ModelInfo,
    ProviderStatus,
    RewriteResult,
)
from studio.secrets_store import delete_secret, get_secret, set_secret

PROVIDER_ID = "chatgpt"
TOKEN_SECRET = "ai_chatgpt_token"
STATE_SECRET = "ai_chatgpt_oauth_state"


class ChatGPTProvider:
    id = PROVIDER_ID
    display_name = "ChatGPT"
    blurb = "Use your eligible ChatGPT plan."
    auth_kind = "oauth"
    priority = 10
    recommended = False
    card_title = "ChatGPT"
    card_subtitle = "Use your eligible ChatGPT plan"
    commercial_gate = True

    def get_status(self) -> ProviderStatus:
        token = get_secret(TOKEN_SECRET)
        eligible = get_secret("ai_chatgpt_commercial_ok") == "1"
        if token:
            detail = "Connected. Plan use requires chatgpt.tokens.use.direct grant."
        elif eligible:
            detail = "Ready to connect with Sign in with ChatGPT (PKCE)."
        else:
            detail = (
                "Sign in with ChatGPT is documented by OpenAI. "
                "A paid or hosted build needs OpenAI approval first. "
                "Personal/open-source local use may proceed once client id is configured."
            )
        return ProviderStatus(
            id=self.id,
            connected=bool(token),
            label=self.display_name,
            detail=detail,
            auth_kind="oauth",
            account_hint=(f"…{token[-4:]}" if token and len(token) >= 4 else ""),
            models=[ModelInfo(id="gpt-4.1-mini", label="ChatGPT plan model")] if token else [],
            can_rewrite=bool(token),
            commercial_note=(
                "Nov 4 2026 terms: users must be able to use this without paying you "
                "or upgrading your app. Seek commercial approval before selling."
            ),
        )

    def connect_start(self, callback_base: str) -> ConnectionResult:
        client_id = get_secret("ai_chatgpt_client_id")
        if not client_id:
            return ConnectionResult(
                ok=False,
                provider_id=self.id,
                message=(
                    "ChatGPT connect needs an OpenAI app client id. "
                    "See developers.openai.com cookbook: Sign in with ChatGPT. "
                    "Until then, use Free AI (OpenRouter)."
                ),
                redirect_url="https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt",
            )
        state = secrets.token_urlsafe(16)
        set_secret(STATE_SECRET, state)
        # Placeholder authorize URL — real endpoints come from OpenAI app registration
        callback = f"{callback_base.rstrip('/')}/ai/callback/chatgpt"
        url = (
            "https://auth.openai.com/oauth/authorize?"
            f"response_type=code&client_id={client_id}&redirect_uri={callback}"
            f"&scope=openid%20profile%20chatgpt.tokens.use.direct&state={state}"
        )
        return ConnectionResult(
            ok=True,
            provider_id=self.id,
            message="Continue in your browser to Sign in with ChatGPT.",
            redirect_url=url,
        )

    def connect_finish(self, **kwargs) -> ConnectionResult:
        # Full token exchange requires registered client secret/PKCE per OpenAI cookbook.
        token = (kwargs.get("api_key") or kwargs.get("access_token") or "").strip()
        if token:
            set_secret(TOKEN_SECRET, token)
            return ConnectionResult(ok=True, provider_id=self.id, message="ChatGPT token saved.")
        return ConnectionResult(
            ok=False,
            provider_id=self.id,
            message="Complete Sign in with ChatGPT in the browser, or paste a granted token in Advanced.",
        )

    def disconnect(self) -> None:
        delete_secret(TOKEN_SECRET)
        delete_secret(STATE_SECRET)

    def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="gpt-4.1-mini", label="ChatGPT")]

    def rewrite(self, request: EvidenceBoundRequest) -> RewriteResult:
        token = get_secret(TOKEN_SECRET)
        if not token:
            return RewriteResult(ok=False, error="ChatGPT not connected", provider_id=self.id)
        # Responses API call would go here once client is registered.
        return RewriteResult(
            ok=False,
            error="ChatGPT Responses API rewrite awaits registered OpenAI app credentials.",
            provider_id=self.id,
        )
