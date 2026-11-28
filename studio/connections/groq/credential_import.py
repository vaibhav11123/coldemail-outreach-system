"""Explicit credential import — paste or consented local env detection.

Forbidden: reading Groq session cookies, scraping the dashboard, capturing passwords,
or calling undocumented account-management endpoints.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

_KEY_HINT = re.compile(r"^gsk_[A-Za-z0-9]{16,}$")


@dataclass
class ImportedCredential:
    key: str
    source: str  # paste | local_env | reconnect
    format_looks_valid: bool


def normalize_pasted_key(raw: str) -> str:
    text = (raw or "").strip()
    # Students sometimes paste surrounding quotes or "Bearer …"
    if text.lower().startswith("bearer "):
        text = text[7:].strip()
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        text = text[1:-1].strip()
    return text


def from_explicit_paste(raw: str) -> ImportedCredential | None:
    key = normalize_pasted_key(raw)
    if not key:
        return None
    return ImportedCredential(
        key=key,
        source="paste",
        format_looks_valid=bool(_KEY_HINT.match(key)),
    )


def peek_local_env_key() -> dict:
    """Detect a locally configured GROQ_API_KEY without importing it.

    Never auto-imports. The student must consent on the assistant screen.
    Product-managed STUDIO_GROQ_API_KEY is ignored (not a student credential).
    """
    student = (os.environ.get("GROQ_API_KEY") or "").strip()
    # Do not treat STUDIO_GROQ_API_KEY as the student's key
    if not student:
        return {"found": False, "hint": "", "source": ""}
    hint = f"…{student[-4:]}" if len(student) >= 4 else "…****"
    return {
        "found": True,
        "hint": hint,
        "source": "GROQ_API_KEY",
        "format_looks_valid": bool(_KEY_HINT.match(student)),
    }


def from_local_env_with_consent(*, consented: bool) -> ImportedCredential | None:
    if not consented:
        return None
    student = (os.environ.get("GROQ_API_KEY") or "").strip()
    if not student:
        return None
    return ImportedCredential(
        key=student,
        source="local_env",
        format_looks_valid=bool(_KEY_HINT.match(student)),
    )
