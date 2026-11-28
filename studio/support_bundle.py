"""Support bundle with redaction of emails, tokens, and bodies."""

from __future__ import annotations

import json
import re
from typing import Any

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
REDACT_KEYS = {"email", "token", "password", "body", "api_key", "authorization", "secret"}


def _redact(value: Any, key: str | None = None) -> Any:
    if key and key.lower() in REDACT_KEYS:
        return "[REDACTED]"
    if isinstance(value, str):
        return EMAIL_RE.sub("[REDACTED_EMAIL]", value)
    if isinstance(value, dict):
        return {k: _redact(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def build_support_bundle(payload: dict[str, Any]) -> str:
    safe = _redact(payload)
    return json.dumps(safe, indent=2, sort_keys=True)
