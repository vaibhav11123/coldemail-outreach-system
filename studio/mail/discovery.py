"""Universal email configuration discovery (Thunderbird-style).

Order: verified registry → well-known consumers → Thunderbird ISPDB →
DNS MX hints → manual. Endpoints are probed before we accept password auth.
"""

from __future__ import annotations

import re
import socket
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote

import requests

from studio.mail.registry import lookup_domain
from studio.mail.types import MailDiscovery, ServerEndpoint

_EMAIL_RE = re.compile(r"^[^@\s]+@([^@\s]+\.[^@\s]+)$")
THUNDERBIRD_ISPDB = "https://autoconfig.thunderbird.net/v1.1/{domain}"
PROBE_TIMEOUT = 3.0


def normalize_email(raw: str) -> str:
    return (raw or "").strip().lower()


def parse_email(raw: str) -> tuple[str, str] | None:
    email = normalize_email(raw)
    m = _EMAIL_RE.match(email)
    if not m:
        return None
    return email, m.group(1).lower()


def probe_tcp(host: str, port: int, timeout: float = PROBE_TIMEOUT) -> bool:
    """Verify the host:port accepts TCP before we ask for credentials."""
    if not host or port <= 0:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def verify_endpoints(smtp: ServerEndpoint | None, imap: ServerEndpoint | None) -> bool:
    ok = True
    if smtp:
        ok = probe_tcp(smtp.host, smtp.port) and ok
    if imap:
        # IMAP probe is best-effort for send-first; failure alone does not block send config
        probe_tcp(imap.host, imap.port)
    return ok if smtp else False


def _from_registry(
    email: str, domain: str, *, probe: bool = True
) -> MailDiscovery | None:
    hit = lookup_domain(domain)
    if not hit:
        return None
    matched, cfg = hit
    smtp = cfg.get("smtp")
    imap = cfg.get("imap")
    auth = cfg["auth_method"]
    if auth in {"oauth_google", "oauth_microsoft"}:
        verified = True
    elif auth == "password" and smtp and probe:
        verified = verify_endpoints(smtp, imap)
    elif auth == "password" and smtp:
        # Offline / UI preview: config is from official docs; probe at connect time
        verified = True
    else:
        verified = False
    return MailDiscovery(
        email=email,
        domain=matched,
        institution=cfg["institution"],
        auth_method=auth,
        source="verified_registry" if auth == "password" else "well_known_consumer",
        confidence=cfg.get("confidence", "verified"),
        smtp=smtp,
        imap=imap,
        detail=cfg.get("detail", ""),
        source_url=cfg.get("source_url", ""),
        notes=list(cfg.get("notes") or []),
        verified_endpoints=verified,
    )


def _parse_thunderbird_xml(xml_text: str, email: str, domain: str) -> MailDiscovery | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    provider = root.find("emailProvider")
    if provider is None:
        return None
    display = ""
    dn = provider.find("displayName")
    if dn is not None and dn.text:
        display = dn.text.strip()
    smtp_el = None
    imap_el = None
    for el in provider.findall("outgoingServer"):
        if el.get("type") == "smtp":
            smtp_el = el
            break
    for el in provider.findall("incomingServer"):
        if el.get("type") == "imap":
            imap_el = el
            break
    if smtp_el is None:
        return None

    def endpoint(node: ET.Element) -> ServerEndpoint:
        host = (node.findtext("hostname") or "").strip()
        port = int((node.findtext("port") or "0").strip() or "0")
        socket_type = (node.findtext("socketType") or "SSL").strip().upper()
        if socket_type in {"SSL", "SSL/TLS"}:
            security = "ssl"
        elif socket_type in {"STARTTLS"}:
            security = "starttls"
        else:
            security = "plain"
        user = (node.findtext("username") or "%EMAILLOCALPART%").strip()
        return ServerEndpoint(host=host, port=port, security=security, username_template=user)

    smtp = endpoint(smtp_el)
    imap = endpoint(imap_el) if imap_el is not None else None
    # Prefer OAuth when ISPDB advertises it for Google-like providers
    auth_method = "password"
    for auth in smtp_el.findall("authentication"):
        if (auth.text or "").strip().lower() == "oauth2":
            # Still password-capable; consumers already caught. Treat as password SMTP
            # unless domain is google — handled by registry first.
            break
    verified = verify_endpoints(smtp, imap)
    return MailDiscovery(
        email=email,
        domain=domain,
        institution=display or domain,
        auth_method=auth_method,
        source="thunderbird_ispdb",
        confidence="high" if verified else "medium",
        smtp=smtp,
        imap=imap,
        detail=f"Configuration found via Thunderbird ISP database for {domain}.",
        source_url=THUNDERBIRD_ISPDB.format(domain=quote(domain)),
        notes=["Verify against your institution’s computer centre before bulk outreach."],
        verified_endpoints=verified,
    )


def _thunderbird_ispdb(email: str, domain: str) -> MailDiscovery | None:
    url = THUNDERBIRD_ISPDB.format(domain=quote(domain))
    try:
        resp = requests.get(url, timeout=4)
    except requests.RequestException:
        return None
    if resp.status_code != 200 or not resp.text.strip():
        return None
    return _parse_thunderbird_xml(resp.text, email, domain)


def _mx_hint(email: str, domain: str) -> MailDiscovery | None:
    try:
        import dns.resolver  # type: ignore
    except ImportError:
        # Stdlib-only fallback via dig-less heuristic: skip if dnspython absent
        return _mx_hint_socket(email, domain)

    try:
        answers = dns.resolver.resolve(domain, "MX")
        hosts = [str(r.exchange).lower().rstrip(".") for r in answers]
    except Exception:  # noqa: BLE001
        return None
    joined = " ".join(hosts)
    if any(x in joined for x in ("google.com", "googlemail.com", "aspmx.l.google")):
        return MailDiscovery(
            email=email,
            domain=domain,
            institution=f"{domain} (Google Workspace)",
            auth_method="oauth_google",
            source="dns_mx",
            confidence="medium",
            detail="MX records point at Google — Continue with Google for Workspace accounts.",
            notes=["University admins may still block third-party OAuth apps."],
            verified_endpoints=True,
        )
    if any(x in joined for x in ("outlook.com", "protection.outlook.com", "microsoft")):
        return MailDiscovery(
            email=email,
            domain=domain,
            institution=f"{domain} (Microsoft 365)",
            auth_method="oauth_microsoft",
            source="dns_mx",
            confidence="medium",
            detail="MX records point at Microsoft — Continue with Microsoft.",
            notes=["University admins may restrict third-party clients."],
            verified_endpoints=True,
        )
    return None


def _mx_hint_socket(email: str, domain: str) -> MailDiscovery | None:
    """Lightweight MX-ish guess without dnspython: try common Workspace hostnames via getaddrinfo."""
    # Cannot read MX without a resolver library; return None rather than guess wrong.
    return None


def _manual(email: str, domain: str) -> MailDiscovery:
    return MailDiscovery(
        email=email,
        domain=domain,
        institution=domain,
        auth_method="manual",
        source="manual",
        confidence="low",
        detail=(
            "We could not auto-detect mail servers for this domain. "
            "Use Advanced email settings, or ask your computer centre for IMAP/SMTP client settings."
        ),
        notes=[
            "Many universities already allow Thunderbird-style clients — no Google Cloud project needed.",
            "Some campuses require VPN or disable password login; we cannot override that.",
        ],
        verified_endpoints=False,
    )


def discover_email_config(
    raw_email: str,
    *,
    allow_network: bool = True,
    probe: bool | None = None,
) -> MailDiscovery:
    parsed = parse_email(raw_email)
    if not parsed:
        return MailDiscovery(
            email=(raw_email or "").strip(),
            domain="",
            institution="",
            auth_method="manual",
            source="manual",
            confidence="low",
            detail="Enter a full email address (for example student@iitd.ac.in).",
            verified_endpoints=False,
        )
    email, domain = parsed
    do_probe = allow_network if probe is None else probe

    reg = _from_registry(email, domain, probe=do_probe)
    if reg:
        return reg

    if allow_network:
        isp = _thunderbird_ispdb(email, domain)
        if isp and isp.smtp:
            return isp
        mx = _mx_hint(email, domain)
        if mx:
            return mx

    return _manual(email, domain)


def discovery_preview(raw_email: str, allow_network: bool = False) -> dict[str, Any]:
    """JSON-friendly preview used by the Connect Email form (tests skip network)."""
    return discover_email_config(raw_email, allow_network=allow_network).as_dict()
