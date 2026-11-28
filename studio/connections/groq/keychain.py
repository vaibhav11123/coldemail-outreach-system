"""Persist Groq credentials via the studio OS keychain / local secrets store."""

from __future__ import annotations

from studio.secrets_store import delete_secret, get_secret, set_secret

KEY_SECRET = "ai_groq_key"
MODEL_SECRET = "ai_groq_model"
VALIDATED_SECRET = "ai_groq_validated"
SOURCE_SECRET = "ai_groq_key_source"


def store_validated_key(api_key: str, model: str, *, source: str) -> None:
    set_secret(KEY_SECRET, api_key)
    set_secret(MODEL_SECRET, model)
    set_secret(VALIDATED_SECRET, "1")
    set_secret(SOURCE_SECRET, source)
    # Clear legacy managed-proxy secrets from earlier builds
    delete_secret("ai_groq_managed_enabled")
    delete_secret("ai_groq_managed_key")


def clear_stored_key() -> None:
    delete_secret(KEY_SECRET)
    delete_secret(MODEL_SECRET)
    delete_secret(VALIDATED_SECRET)
    delete_secret(SOURCE_SECRET)
    delete_secret("ai_groq_managed_enabled")
    delete_secret("ai_groq_managed_key")


def get_stored_key() -> str:
    return (get_secret(KEY_SECRET) or "").strip()


def get_selected_model() -> str:
    from studio.connections.groq.model_discovery import DEFAULT_MODEL

    return (get_secret(MODEL_SECRET) or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def is_connected() -> bool:
    return bool(get_stored_key()) and get_secret(VALIDATED_SECRET) == "1"


def mark_revoked() -> None:
    delete_secret(VALIDATED_SECRET)


def account_hint() -> str:
    key = get_stored_key()
    if key and len(key) >= 4:
        return f"…{key[-4:]}"
    return ""
