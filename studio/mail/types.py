"""Shared mail configuration types."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

AuthMethod = Literal[
    "oauth_google",
    "oauth_microsoft",
    "password",
    "manual",
]
SocketSecurity = Literal["ssl", "starttls", "plain"]
DiscoverySource = Literal[
    "verified_registry",
    "thunderbird_ispdb",
    "dns_mx",
    "well_known_consumer",
    "manual",
]


@dataclass
class ServerEndpoint:
    host: str
    port: int
    security: SocketSecurity = "ssl"
    username_template: str = "%EMAILLOCALPART%"  # or %EMAILADDRESS%

    def resolved_username(self, email: str) -> str:
        local, _, _ = email.partition("@")
        if self.username_template == "%EMAILADDRESS%":
            return email
        return local

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MailDiscovery:
    email: str
    domain: str
    institution: str
    auth_method: AuthMethod
    source: DiscoverySource
    confidence: str  # verified | high | medium | low
    smtp: ServerEndpoint | None = None
    imap: ServerEndpoint | None = None
    detail: str = ""
    source_url: str = ""
    notes: list[str] = field(default_factory=list)
    verified_endpoints: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "email": self.email,
            "domain": self.domain,
            "institution": self.institution,
            "auth_method": self.auth_method,
            "source": self.source,
            "confidence": self.confidence,
            "smtp": self.smtp.as_dict() if self.smtp else None,
            "imap": self.imap.as_dict() if self.imap else None,
            "detail": self.detail,
            "source_url": self.source_url,
            "notes": list(self.notes),
            "verified_endpoints": self.verified_endpoints,
        }
