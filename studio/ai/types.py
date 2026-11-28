"""Shared types for BYOAI providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


AuthKind = Literal[
    "oauth",
    "device",
    "detect",
    "guided_key",
    "custom",
    "unavailable",
]


@dataclass
class ModelInfo:
    id: str
    label: str
    free: bool = False


@dataclass
class ProviderStatus:
    id: str
    connected: bool
    label: str
    detail: str = ""
    auth_kind: AuthKind = "guided_key"
    account_hint: str = ""  # last-4 or email, never full secret
    models: list[ModelInfo] = field(default_factory=list)
    can_rewrite: bool = False
    commercial_note: str = ""


@dataclass
class EvidenceBoundRequest:
    recipient: str
    subject: str
    body: str
    evidence_snippets: list[str]
    citations: list[dict[str, str]] = field(default_factory=list)
    researcher_name: str = ""


@dataclass
class RewriteResult:
    ok: bool
    subject: str = ""
    body: str = ""
    provider_id: str = ""
    model: str = ""
    error: str = ""
    used_deterministic_fallback: bool = False
    rejected_claims: list[str] = field(default_factory=list)


@dataclass
class ConnectionResult:
    ok: bool
    provider_id: str
    message: str = ""
    redirect_url: str | None = None
    needs_paste_code: bool = False
    extra: dict[str, Any] = field(default_factory=dict)
