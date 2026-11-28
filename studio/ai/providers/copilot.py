"""GitHub Copilot SDK device login — student plans; use-case verification pending."""

from __future__ import annotations

from studio.ai.types import (
    ConnectionResult,
    EvidenceBoundRequest,
    ModelInfo,
    ProviderStatus,
    RewriteResult,
)
from studio.secrets_store import delete_secret, get_secret, set_secret

PROVIDER_ID = "copilot"
TOKEN_SECRET = "ai_copilot_token"


class CopilotProvider:
    id = PROVIDER_ID
    display_name = "GitHub Copilot"
    blurb = "Supports eligible student accounts."
    auth_kind = "device"
    priority = 20
    recommended = False
    card_title = "GitHub Copilot"
    card_subtitle = "Supports eligible student accounts"

    def get_status(self) -> ProviderStatus:
        token = get_secret(TOKEN_SECRET)
        return ProviderStatus(
            id=self.id,
            connected=bool(token),
            label=self.display_name,
            detail=(
                "Connected via device login."
                if token
                else (
                    "Uses GitHub device login (no key copy). "
                    "Filesystem, shell, and agent tools stay disabled for rewrite. "
                    "Confirm research-letter use is permitted under Copilot terms before relying on this path."
                )
            ),
            auth_kind="device",
            account_hint=(f"…{token[-4:]}" if token and len(token) >= 4 else ""),
            models=[ModelInfo(id="copilot", label="Copilot")] if token else [],
            can_rewrite=bool(token),
            commercial_note="Verify non-coding correspondence is allowed under Copilot terms.",
        )

    def connect_start(self, callback_base: str) -> ConnectionResult:
        # Device-flow scaffolding: real SDK would return user_code + verification_uri
        return ConnectionResult(
            ok=True,
            provider_id=self.id,
            message=(
                "Copilot uses GitHub device login. Open github.com/login/device, "
                "enter the code shown by the Copilot SDK, then return here. "
                "SDK wiring lands when student-plan smoke tests pass."
            ),
            redirect_url="https://github.com/login/device",
            needs_paste_code=True,
            extra={"paste_kind": "device_token"},
        )

    def connect_finish(self, **kwargs) -> ConnectionResult:
        token = (kwargs.get("api_key") or kwargs.get("code") or "").strip()
        if not token:
            return ConnectionResult(
                ok=False,
                provider_id=self.id,
                message="Paste the device token after approving on GitHub.",
            )
        set_secret(TOKEN_SECRET, token)
        return ConnectionResult(ok=True, provider_id=self.id, message="Copilot connected.")

    def disconnect(self) -> None:
        delete_secret(TOKEN_SECRET)

    def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="copilot", label="Copilot")]

    def rewrite(self, request: EvidenceBoundRequest) -> RewriteResult:
        if not get_secret(TOKEN_SECRET):
            return RewriteResult(ok=False, error="Copilot not connected", provider_id=self.id)
        return RewriteResult(
            ok=False,
            error="Copilot SDK rewrite is scaffolded pending terms verification and SDK smoke test.",
            provider_id=self.id,
        )
