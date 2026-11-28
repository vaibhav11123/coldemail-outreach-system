"""Validate a student GroqCloud API key against the official inference API."""

from __future__ import annotations

from dataclasses import dataclass

import requests

from studio.connections.groq.model_discovery import MODELS_URL


@dataclass
class ValidationResult:
    ok: bool
    message: str
    models: list[str]
    kind: str = "ok"  # ok | empty | rejected | rate_limited | unreachable | bad_response


def validate_api_key(api_key: str) -> ValidationResult:
    key = (api_key or "").strip()
    if not key:
        return ValidationResult(
            ok=False,
            message="Paste the key you created in GroqCloud.",
            models=[],
            kind="empty",
        )
    try:
        resp = requests.get(
            MODELS_URL,
            headers={"Authorization": f"Bearer {key}"},
            timeout=20,
        )
    except requests.RequestException as exc:
        return ValidationResult(
            ok=False,
            message=f"Could not reach GroqCloud ({exc}). Check your internet and try again.",
            models=[],
            kind="unreachable",
        )
    if resp.status_code in (401, 403):
        return ValidationResult(
            ok=False,
            message="GroqCloud rejected this key. Create a new key in the console and paste it again.",
            models=[],
            kind="rejected",
        )
    if resp.status_code == 429:
        return ValidationResult(
            ok=False,
            message="Groq rate limit while validating. Wait a moment and try again.",
            models=[],
            kind="rate_limited",
        )
    if resp.status_code >= 400:
        return ValidationResult(
            ok=False,
            message=f"GroqCloud returned HTTP {resp.status_code} while validating.",
            models=[],
            kind="bad_response",
        )
    try:
        data = resp.json()
    except Exception:  # noqa: BLE001
        return ValidationResult(
            ok=False,
            message="GroqCloud returned an unreadable response.",
            models=[],
            kind="bad_response",
        )
    models = []
    for row in data.get("data") or []:
        mid = (row.get("id") or "").strip()
        if mid:
            models.append(mid)
    if not models:
        return ValidationResult(
            ok=False,
            message="Key accepted but no models were listed. Try again later.",
            models=[],
            kind="bad_response",
        )
    return ValidationResult(
        ok=True,
        message="GroqCloud accepted your key. Your own free allowance will be used.",
        models=models,
        kind="ok",
    )
