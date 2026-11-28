"""BYOG — Bring Your Own GroqCloud.

Students connect their own GroqCloud account via a guided one-time setup.
We never operate a shared Groq proxy, never pool quotas, and never label this as OAuth
until Groq documents a third-party delegated authorization flow.
"""

from __future__ import annotations

import re

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
KEY_SECRET = "ai_groq_key"
MODEL_SECRET = "ai_groq_model"
VALIDATED_SECRET = "ai_groq_validated"

# Official console pages (open in system browser)
CONSOLE_KEYS_URL = "https://console.groq.com/keys"
DOCS_URL = "https://console.groq.com/docs/quickstart"
API_BASE = "https://api.groq.com/openai/v1"
CHAT_URL = f"{API_BASE}/chat/completions"
MODELS_URL = f"{API_BASE}/models"

# Prefer short, fast models suitable for evidence-bound letter polish
PREFERRED_MODELS = (
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-120b",
)
DEFAULT_MODEL = PREFERRED_MODELS[0]

_KEY_HINT = re.compile(r"^gsk_[A-Za-z0-9]{20,}$")


def _stored_key() -> str:
    return (get_secret(KEY_SECRET) or "").strip()


def _selected_model() -> str:
    return (get_secret(MODEL_SECRET) or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def validate_groq_key(api_key: str) -> tuple[bool, str, list[str]]:
    """Validate a student key against GroqCloud. Returns (ok, message, model_ids)."""
    key = (api_key or "").strip()
    if not key:
        return False, "Paste the key you created in GroqCloud.", []
    try:
        resp = requests.get(
            MODELS_URL,
            headers={"Authorization": f"Bearer {key}"},
            timeout=20,
        )
    except requests.RequestException as exc:
        return False, f"Could not reach GroqCloud ({exc}). Check your internet and try again.", []
    if resp.status_code in (401, 403):
        return False, "GroqCloud rejected this key. Create a new key in the console and paste it again.", []
    if resp.status_code == 429:
        return False, "Groq rate limit while validating. Wait a moment and try again.", []
    if resp.status_code >= 400:
        return False, f"GroqCloud returned HTTP {resp.status_code} while validating.", []
    try:
        data = resp.json()
    except Exception:  # noqa: BLE001
        return False, "GroqCloud returned an unreadable response.", []
    models = []
    for row in data.get("data") or []:
        mid = (row.get("id") or "").strip()
        if mid:
            models.append(mid)
    if not models:
        return False, "Key accepted but no models were listed. Try again later.", []
    return True, "GroqCloud connected. Your own free allowance will be used.", models


def pick_model(available: list[str]) -> str:
    avail = set(available)
    for mid in PREFERRED_MODELS:
        if mid in avail:
            return mid
    return available[0] if available else DEFAULT_MODEL


class GroqProvider:
    id = PROVIDER_ID
    display_name = "Groq"
    blurb = (
        "Fast AI using your own GroqCloud free allowance. "
        "One-time guided setup — not OAuth (Groq has no public delegated auth yet)."
    )
    auth_kind = "guided_key"
    priority = 0
    recommended = True
    advanced = False
    card_title = "Activate free AI"
    card_subtitle = "GroqCloud — your account, your allowance"

    def get_status(self) -> ProviderStatus:
        key = _stored_key()
        connected = bool(key) and get_secret(VALIDATED_SECRET) == "1"
        if connected:
            detail = (
                f"Connected to GroqCloud. Model {_selected_model()}. "
                "Inference uses your Groq allowance."
            )
        elif key:
            detail = "Key saved but not validated. Open Connect Groq to re-check."
        else:
            detail = (
                "We open GroqCloud; you create a key once, paste it here, "
                "and we store it in your OS keychain. No coding required."
            )
        return ProviderStatus(
            id=self.id,
            connected=connected,
            label=self.display_name,
            detail=detail,
            auth_kind="guided_key",
            account_hint=(f"…{key[-4:]}" if connected and len(key) >= 4 else ""),
            models=self.list_models() if connected else [],
            can_rewrite=connected,
            commercial_note=(
                "Uses your own GroqCloud key and free allowance. "
                "This is a guided connection, not OAuth — Groq documents API keys only today."
            ),
        )

    def connect_start(self, callback_base: str) -> ConnectionResult:
        return ConnectionResult(
            ok=True,
            provider_id=self.id,
            message=(
                "1) Open GroqCloud and sign in. "
                "2) Create an API key for Academic Outreach Studio. "
                "3) Copy it, return here, and paste once. "
                "We validate, pick a model, and store the key in your keychain."
            ),
            redirect_url=CONSOLE_KEYS_URL,
            needs_paste_code=True,
            extra={
                "paste_kind": "api_key",
                "guided_title": "Activate free AI",
                "guided_steps": [
                    "Open GroqCloud (button below) and sign in.",
                    "Create a dedicated API key (name it Academic Outreach Studio).",
                    "Copy the key, then paste it into the field on this page.",
                    "We validate automatically and never show the full key again.",
                ],
                "docs_url": DOCS_URL,
            },
        )

    def connect_finish(self, **kwargs) -> ConnectionResult:
        key = (kwargs.get("api_key") or kwargs.get("code") or "").strip()
        ok, message, models = validate_groq_key(key)
        if not ok:
            return ConnectionResult(ok=False, provider_id=self.id, message=message)
        model = pick_model(models)
        set_secret(KEY_SECRET, key)
        set_secret(MODEL_SECRET, model)
        set_secret(VALIDATED_SECRET, "1")
        # Clear any legacy managed-key flags from earlier builds
        delete_secret("ai_groq_managed_enabled")
        delete_secret("ai_groq_managed_key")
        hint = ""
        if _KEY_HINT.match(key):
            hint = " Key format looks like a Groq key."
        return ConnectionResult(
            ok=True,
            provider_id=self.id,
            message=f"{message} Using model {model}.{hint}",
        )

    def disconnect(self) -> None:
        delete_secret(KEY_SECRET)
        delete_secret(MODEL_SECRET)
        delete_secret(VALIDATED_SECRET)
        delete_secret("ai_groq_managed_enabled")
        delete_secret("ai_groq_managed_key")

    def list_models(self) -> list[ModelInfo]:
        chosen = _selected_model()
        out = [ModelInfo(id=chosen, label=f"{chosen} (selected)", free=True)]
        for mid in PREFERRED_MODELS:
            if mid != chosen:
                out.append(ModelInfo(id=mid, label=mid, free=True))
        return out

    def rewrite(self, request: EvidenceBoundRequest) -> RewriteResult:
        key = _stored_key()
        if not key or get_secret(VALIDATED_SECRET) != "1":
            return RewriteResult(
                ok=False,
                error="Groq not connected. Open Activate free AI to connect your GroqCloud account.",
                provider_id=self.id,
            )
        from studio.ai.engine import REWRITE_SYSTEM

        model = _selected_model()
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
            return RewriteResult(
                ok=False,
                error=f"GroqCloud unreachable ({exc}). Built-in draft can still be used.",
                provider_id=self.id,
            )
        if resp.status_code == 401 or resp.status_code == 403:
            delete_secret(VALIDATED_SECRET)
            return RewriteResult(
                ok=False,
                error="GroqCloud rejected your key. Reconnect under Activate free AI.",
                provider_id=self.id,
            )
        if resp.status_code == 429:
            return RewriteResult(
                ok=False,
                error=(
                    "Groq rate limit reached on your account. "
                    "Wait and retry, or use Free AI (OpenRouter) / built-in draft."
                ),
                provider_id=self.id,
            )
        if resp.status_code >= 500:
            return RewriteResult(
                ok=False,
                error="GroqCloud is temporarily unavailable. Try again or use the built-in draft.",
                provider_id=self.id,
            )
        if resp.status_code >= 400:
            return RewriteResult(
                ok=False,
                error=f"Groq HTTP {resp.status_code}",
                provider_id=self.id,
            )
        try:
            data = resp.json()
            body = data["choices"][0]["message"]["content"].strip()
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            return RewriteResult(ok=False, error="Unexpected Groq response.", provider_id=self.id)
        return RewriteResult(
            ok=True,
            subject=request.subject,
            body=body,
            provider_id=self.id,
            model=model,
        )
