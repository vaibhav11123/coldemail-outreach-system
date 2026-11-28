"""Groq provider — thin adapter over the Groq Connect Assistant (BYOG)."""

from __future__ import annotations

import requests

from studio.ai.types import (
    ConnectionResult,
    EvidenceBoundRequest,
    ModelInfo,
    ProviderStatus,
    RewriteResult,
)
from studio.connections.groq import keychain, onboarding
from studio.connections.groq.browser_launcher import official_docs_url, official_keys_url
from studio.connections.groq.connection_state import ConnectionPhase
from studio.connections.groq.model_discovery import CHAT_URL, PREFERRED_MODELS
from studio.connections.groq.quota_manager import interpret_http_status

# Re-exports for existing tests
KEY_SECRET = keychain.KEY_SECRET
MODEL_SECRET = keychain.MODEL_SECRET
VALIDATED_SECRET = keychain.VALIDATED_SECRET
CONSOLE_KEYS_URL = official_keys_url()
DOCS_URL = official_docs_url()
DEFAULT_MODEL = PREFERRED_MODELS[0]


def validate_groq_key(api_key: str) -> tuple[bool, str, list[str]]:
    from studio.connections.groq.credential_validator import validate_api_key

    result = validate_api_key(api_key)
    return result.ok, result.message, result.models


def pick_model(available: list[str]) -> str:
    from studio.connections.groq.model_discovery import pick_model as _pick

    return _pick(available)


class GroqProvider:
    id = "groq"
    display_name = "Groq"
    blurb = (
        "Connect Assistant opens GroqCloud; you create a key once. "
        "Your allowance, stored on your device — not OAuth."
    )
    auth_kind = "guided_key"
    priority = 0
    recommended = True
    advanced = False
    card_title = "Connect your free AI"
    card_subtitle = "GroqCloud — your account, your allowance"

    def get_status(self) -> ProviderStatus:
        view = onboarding.build_view()
        return ProviderStatus(
            id=self.id,
            connected=view.connected,
            label=self.display_name,
            detail=view.message,
            auth_kind="guided_key",
            account_hint=view.account_hint,
            models=self.list_models() if view.connected else [],
            can_rewrite=view.connected,
            commercial_note=view.compliance_note,
        )

    def connect_start(self, callback_base: str) -> ConnectionResult:
        view = onboarding.start_assistant(launch_browser=False)
        return ConnectionResult(
            ok=True,
            provider_id=self.id,
            message=view.message,
            redirect_url=view.dashboard_url,
            needs_paste_code=True,
            extra={
                "paste_kind": "api_key",
                "guided_title": view.title,
                "guided_steps": view.steps,
                "docs_url": view.docs_url,
                "assistant": True,
                "phase": view.phase.value,
                "local_env": view.local_env,
            },
        )

    def connect_finish(self, **kwargs) -> ConnectionResult:
        if kwargs.get("import_local") in ("1", "true", True):
            ok, message, _view = onboarding.import_local_env_key_with_consent(
                consented=True
            )
        elif kwargs.get("decline_local") in ("1", "true", True):
            ok, message, _view = onboarding.import_local_env_key_with_consent(
                consented=False
            )
            return ConnectionResult(ok=False, provider_id=self.id, message=message)
        else:
            key = (kwargs.get("api_key") or kwargs.get("code") or "").strip()
            ok, message, _view = onboarding.complete_with_pasted_key(key)
        if ok:
            from studio.ai.registry import set_active_provider

            set_active_provider(self.id)
        return ConnectionResult(ok=ok, provider_id=self.id, message=message)

    def disconnect(self) -> None:
        keychain.clear_stored_key()
        onboarding.cancel_setup()

    def list_models(self) -> list[ModelInfo]:
        chosen = keychain.get_selected_model()
        out = [ModelInfo(id=chosen, label=f"{chosen} (selected)", free=True)]
        for mid in PREFERRED_MODELS:
            if mid != chosen:
                out.append(ModelInfo(id=mid, label=mid, free=True))
        return out

    def rewrite(self, request: EvidenceBoundRequest) -> RewriteResult:
        if not keychain.is_connected():
            return RewriteResult(
                ok=False,
                error="Groq not connected. Open Connect your free AI to finish setup.",
                provider_id=self.id,
            )
        from studio.ai.engine import REWRITE_SYSTEM

        model = keychain.get_selected_model()
        key = keychain.get_stored_key()
        payload = {
            "model": model,
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
                CHAT_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60,
            )
        except requests.RequestException as exc:
            onboarding.mark_rewrite_failure(
                "unavailable", f"GroqCloud unreachable ({exc})."
            )
            return RewriteResult(
                ok=False,
                error=f"GroqCloud unreachable ({exc}). Built-in draft can still be used.",
                provider_id=self.id,
            )
        signal = interpret_http_status(resp.status_code)
        if signal.kind != "ok":
            onboarding.mark_rewrite_failure(signal.kind, signal.message)
            return RewriteResult(ok=False, error=signal.message, provider_id=self.id)
        try:
            data = resp.json()
            body = data["choices"][0]["message"]["content"].strip()
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            return RewriteResult(
                ok=False, error="Unexpected Groq response.", provider_id=self.id
            )
        return RewriteResult(
            ok=True,
            subject=request.subject,
            body=body,
            provider_id=self.id,
            model=model,
        )
