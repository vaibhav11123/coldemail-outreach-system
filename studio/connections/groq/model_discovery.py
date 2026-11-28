"""Discover and select Groq models for evidence-bound letter polish."""

from __future__ import annotations

API_BASE = "https://api.groq.com/openai/v1"
MODELS_URL = f"{API_BASE}/models"
CHAT_URL = f"{API_BASE}/chat/completions"

PREFERRED_MODELS = (
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-120b",
)
DEFAULT_MODEL = PREFERRED_MODELS[0]


def pick_model(available: list[str]) -> str:
    avail = set(available)
    for mid in PREFERRED_MODELS:
        if mid in avail:
            return mid
    return available[0] if available else DEFAULT_MODEL


def describe_models(available: list[str], selected: str) -> list[dict]:
    out = [{"id": selected, "label": f"{selected} (selected)", "selected": True}]
    for mid in available:
        if mid == selected:
            continue
        if mid in PREFERRED_MODELS or len(out) < 6:
            out.append({"id": mid, "label": mid, "selected": False})
        if len(out) >= 6:
            break
    return out
