"""Connection registry types — CON-01…CON-18 readiness model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

AuthMethod = Literal[
    "none",
    "oauth",
    "email_activation",
    "password",
    "public",
    "local_detect",
    "paste_url",
    "paste_id",
    "file_picker",
    "managed",
    "disabled",
    "mcp",
]

ProductionStatus = Literal[
    "production_ready",  # live auth + ops verified — rare
    "documented",  # interface documented; mocked/offline tests OK
    "adapter_ready",  # code path exists; needs vendor clearance or live test
    "clearance_required",
    "unavailable",
]

Priority = Literal["P0", "P1", "conditional", "optional"]


@dataclass
class ConnectionSpec:
    id: str
    title: str
    section: str  # email | ai | research | profile | documents
    purpose: str
    auth_method: AuthMethod
    priority: Priority
    production_status: ProductionStatus
    capabilities: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)  # incremental scopes
    docs_url: str = ""
    fallback: str = ""
    commercial_note: str = ""
    connect_href: str = ""  # in-app path or action
    button_label: str = "Connect"
    required: bool = False  # CON-01: always False for core


@dataclass
class ConnectionStatus:
    connected: bool = False
    detail: str = ""
    account_hint: str = ""
    quota: str = ""
    can_disconnect: bool = False
    disabled_reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConnectionCard:
    spec: ConnectionSpec
    status: ConnectionStatus

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self.spec),
            "status": self.status.as_dict(),
            "available": self.spec.production_status
            in {"production_ready", "documented", "adapter_ready"},
        }
