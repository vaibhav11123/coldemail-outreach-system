"""Provider registry and active-provider selection."""

from __future__ import annotations

from typing import Any

from studio.ai.providers.chatgpt import ChatGPTProvider
from studio.ai.providers.claude import ClaudeProvider
from studio.ai.providers.copilot import CopilotProvider
from studio.ai.providers.custom import CustomProvider
from studio.ai.providers.gemini import GeminiProvider
from studio.ai.providers.grok import GrokProvider
from studio.ai.providers.groq_managed import GroqManagedProvider
from studio.ai.providers.huggingface import HuggingFaceProvider
from studio.ai.providers.ollama import OllamaProvider
from studio.ai.providers.openrouter import OpenRouterProvider
from studio.secrets_store import delete_secret, get_secret, set_secret

ACTIVE_PROVIDER_KEY = "ai_active_provider"

_PROVIDERS: list[Any] = [
    OpenRouterProvider(),
    GroqManagedProvider(),
    ChatGPTProvider(),
    CopilotProvider(),
    HuggingFaceProvider(),
    GeminiProvider(),
    OllamaProvider(),
    ClaudeProvider(),
    GrokProvider(),
    CustomProvider(),
]


def all_providers() -> list[Any]:
    return sorted(_PROVIDERS, key=lambda p: (p.priority, p.display_name))


def get_provider(provider_id: str) -> Any | None:
    for p in _PROVIDERS:
        if p.id == provider_id:
            return p
    return None


def list_provider_cards() -> list[dict[str, Any]]:
    cards = []
    active = get_secret(ACTIVE_PROVIDER_KEY)
    for p in all_providers():
        status = p.get_status()
        cards.append(
            {
                "id": p.id,
                "title": getattr(p, "card_title", p.display_name),
                "subtitle": getattr(p, "card_subtitle", p.blurb),
                "blurb": p.blurb,
                "auth_kind": p.auth_kind,
                "recommended": getattr(p, "recommended", False),
                "advanced": getattr(p, "advanced", False),
                "status": status,
                "is_active": active == p.id and status.connected,
                "button_label": _button_label(p, status),
            }
        )
    return cards


def _button_label(provider: Any, status) -> str:
    if status.connected:
        return "Connected"
    kind = getattr(provider, "auth_kind", "")
    if kind == "oauth":
        return "Connect"
    if kind == "detect":
        return "Detect"
    if kind == "device":
        return "Connect"
    if kind == "unavailable":
        return "Not available yet"
    if kind == "managed":
        return "Enable" if not status.connected else "Connected"
    return "Set up"


def get_active_provider() -> Any | None:
    active = get_secret(ACTIVE_PROVIDER_KEY)
    if active:
        p = get_provider(active)
        if p and p.get_status().connected:
            return p
    # Prefer any connected recommended provider
    for p in all_providers():
        st = p.get_status()
        if st.connected and st.can_rewrite:
            return p
    return None


def set_active_provider(provider_id: str) -> None:
    set_secret(ACTIVE_PROVIDER_KEY, provider_id)


def disconnect_provider(provider_id: str) -> None:
    p = get_provider(provider_id)
    if p:
        p.disconnect()
    if get_secret(ACTIVE_PROVIDER_KEY) == provider_id:
        delete_secret(ACTIVE_PROVIDER_KEY)


def continue_without_ai() -> None:
    delete_secret(ACTIVE_PROVIDER_KEY)
