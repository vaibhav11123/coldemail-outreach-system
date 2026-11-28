"""Hugging Face OAuth with inference-api scope — secondary free path."""

from __future__ import annotations

import secrets
from urllib.parse import urlencode

from studio.ai.types import (
    ConnectionResult,
    EvidenceBoundRequest,
    ModelInfo,
    ProviderStatus,
    RewriteResult,
)
from studio.secrets_store import delete_secret, get_secret, set_secret

PROVIDER_ID = "huggingface"
TOKEN_SECRET = "ai_hf_token"
STATE_SECRET = "ai_hf_oauth_state"
CLIENT_ID_SECRET = "ai_hf_client_id"


class HuggingFaceProvider:
    id = PROVIDER_ID
    display_name = "Hugging Face"
    blurb = "Sign in with Hugging Face for inference-api access."
    auth_kind = "oauth"
    priority = 25
    recommended = False
    card_title = "Hugging Face"
    card_subtitle = "Sign in for inference access"
    advanced = False

    def get_status(self) -> ProviderStatus:
        token = get_secret(TOKEN_SECRET)
        return ProviderStatus(
            id=self.id,
            connected=bool(token),
            label=self.display_name,
            detail=(
                "Connected with inference-api permission."
                if token
                else (
                    "Official HF OAuth supports an inference-api permission so the app "
                    "can run inference on your behalf without a manually copied key. "
                    "Register a public OAuth app (loopback redirect) to enable Connect."
                )
            ),
            auth_kind="oauth",
            account_hint=(f"…{token[-4:]}" if token and len(token) >= 4 else ""),
            models=[ModelInfo(id="hf-inference", label="HF Inference", free=True)] if token else [],
            can_rewrite=bool(token),
        )

    def connect_start(self, callback_base: str) -> ConnectionResult:
        client_id = get_secret(CLIENT_ID_SECRET)
        if not client_id:
            return ConnectionResult(
                ok=False,
                provider_id=self.id,
                message=(
                    "Add a Hugging Face OAuth app client id (public app, no secret) "
                    "to enable one-click connect. Until then, use Free AI."
                ),
                redirect_url="https://huggingface.co/docs/hub/oauth",
            )
        state = secrets.token_urlsafe(16)
        set_secret(STATE_SECRET, state)
        callback = f"{callback_base.rstrip('/')}/ai/callback/huggingface"
        params = {
            "client_id": client_id,
            "redirect_uri": callback,
            "response_type": "code",
            "scope": "openid profile inference-api",
            "state": state,
        }
        url = f"https://huggingface.co/oauth/authorize?{urlencode(params)}"
        return ConnectionResult(
            ok=True,
            provider_id=self.id,
            message="Continue with Hugging Face sign-in.",
            redirect_url=url,
        )

    def connect_finish(self, **kwargs) -> ConnectionResult:
        token = (kwargs.get("api_key") or kwargs.get("access_token") or "").strip()
        if token:
            set_secret(TOKEN_SECRET, token)
            return ConnectionResult(ok=True, provider_id=self.id, message="Hugging Face connected.")
        return ConnectionResult(
            ok=False,
            provider_id=self.id,
            message="Complete HF OAuth in the browser (token exchange needs registered client).",
        )

    def disconnect(self) -> None:
        delete_secret(TOKEN_SECRET)
        delete_secret(STATE_SECRET)

    def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="hf-inference", label="HF Inference", free=True)]

    def rewrite(self, request: EvidenceBoundRequest) -> RewriteResult:
        if not get_secret(TOKEN_SECRET):
            return RewriteResult(ok=False, error="Hugging Face not connected", provider_id=self.id)
        return RewriteResult(
            ok=False,
            error="HF inference rewrite awaits registered OAuth client smoke test.",
            provider_id=self.id,
        )
