"""Institutional SMTP/IMAP connect — credentials stay in local secrets store."""

from __future__ import annotations

from typing import Any

from studio.mail.discovery import discover_email_config, normalize_email, parse_email
from studio.mail.types import MailDiscovery, ServerEndpoint
from studio.secrets_store import delete_secret, get_secret, set_secret

PROVIDER_SECRET = "mail_active_provider"
INSTITUTION_SECRET = "mail_institution"
EMAIL_SECRET = "smtp_sender"
USER_SECRET = "smtp_username"
PASS_SECRET = "smtp_password"
HOST_SECRET = "smtp_host"
PORT_SECRET = "smtp_port"
SSL_SECRET = "smtp_use_ssl"
TLS_SECRET = "smtp_use_tls"
IMAP_HOST_SECRET = "imap_host"
IMAP_PORT_SECRET = "imap_port"
IMAP_SSL_SECRET = "imap_use_ssl"
SOURCE_SECRET = "mail_config_source"


def institute_status() -> dict[str, Any]:
    provider = get_secret(PROVIDER_SECRET) or ""
    connected = provider in {"institute", "smtp"} and bool(
        get_secret(HOST_SECRET) and get_secret(EMAIL_SECRET)
    )
    return {
        "connected": connected,
        "email": get_secret(EMAIL_SECRET) or "",
        "institution": get_secret(INSTITUTION_SECRET) or "",
        "provider": provider,
        "permissions": "Send via institutional SMTP",
        "imap_ready": bool(get_secret(IMAP_HOST_SECRET)),
        "detail": (
            f"Connected to {get_secret(INSTITUTION_SECRET) or 'institutional mail'}."
            if connected
            else "Not connected."
        ),
    }


def smtp_config_from_store() -> dict[str, Any] | None:
    host = get_secret(HOST_SECRET)
    sender = get_secret(EMAIL_SECRET)
    if not host or not sender:
        return None
    use_ssl = get_secret(SSL_SECRET) == "1"
    use_tls = get_secret(TLS_SECRET) == "1"
    return {
        "host": host,
        "port": int(get_secret(PORT_SECRET) or (465 if use_ssl else 587)),
        "username": get_secret(USER_SECRET) or "",
        "password": get_secret(PASS_SECRET) or "",
        "sender": sender,
        "use_ssl": use_ssl,
        "use_tls": use_tls and not use_ssl,
    }


def connect_institute(
    email: str,
    username: str,
    password: str,
    discovery: MailDiscovery | None = None,
    *,
    allow_network: bool = True,
) -> dict[str, Any]:
    email = normalize_email(email)
    if not parse_email(email):
        return {"ok": False, "message": "Enter a valid institutional email address."}
    if not password:
        return {"ok": False, "message": "Institute mail password is required."}
    disc = discovery or discover_email_config(email, allow_network=allow_network)
    if disc.auth_method != "password" or not disc.smtp:
        return {
            "ok": False,
            "message": (
                "This address is not configured for password SMTP. "
                "Use Continue with Google/Microsoft, or Advanced manual settings."
            ),
        }
    # Always probe at connect time — never store credentials if SMTP is unreachable
    from studio.mail import discovery as discovery_mod

    if not discovery_mod.verify_endpoints(disc.smtp, disc.imap):
        return {
            "ok": False,
            "message": (
                f"Could not reach {disc.smtp.host}:{disc.smtp.port}. "
                "Check campus VPN or try again later. Credentials were not saved."
            ),
        }
    disc.verified_endpoints = True

    smtp = disc.smtp
    user = (username or "").strip() or smtp.resolved_username(email)
    set_secret(PROVIDER_SECRET, "institute")
    set_secret(INSTITUTION_SECRET, disc.institution)
    set_secret(EMAIL_SECRET, email)
    set_secret(USER_SECRET, user)
    set_secret(PASS_SECRET, password)
    set_secret(HOST_SECRET, smtp.host)
    set_secret(PORT_SECRET, str(smtp.port))
    if smtp.security == "ssl":
        set_secret(SSL_SECRET, "1")
        set_secret(TLS_SECRET, "0")
    elif smtp.security == "starttls":
        set_secret(SSL_SECRET, "0")
        set_secret(TLS_SECRET, "1")
    else:
        set_secret(SSL_SECRET, "0")
        set_secret(TLS_SECRET, "0")
    if disc.imap:
        set_secret(IMAP_HOST_SECRET, disc.imap.host)
        set_secret(IMAP_PORT_SECRET, str(disc.imap.port))
        set_secret(IMAP_SSL_SECRET, "1" if disc.imap.security == "ssl" else "0")
    set_secret(SOURCE_SECRET, disc.source)
    return {
        "ok": True,
        "message": f"Connected {email} via {disc.institution} institutional mail.",
        "institution": disc.institution,
    }


def connect_manual_smtp(
    *,
    host: str,
    port: str,
    username: str,
    password: str,
    sender: str,
    use_tls: bool,
    use_ssl: bool = False,
) -> dict[str, Any]:
    if not host.strip() or not sender.strip():
        return {"ok": False, "message": "Host and From address are required."}
    port_i = int(port or (465 if use_ssl else 587))
    if use_ssl or port_i == 465:
        use_ssl, use_tls = True, False
    set_secret(PROVIDER_SECRET, "smtp")
    set_secret(INSTITUTION_SECRET, "Manual SMTP")
    set_secret(HOST_SECRET, host.strip())
    set_secret(PORT_SECRET, str(port_i))
    set_secret(USER_SECRET, username)
    if password:
        set_secret(PASS_SECRET, password)
    set_secret(EMAIL_SECRET, sender.strip())
    set_secret(SSL_SECRET, "1" if use_ssl else "0")
    set_secret(TLS_SECRET, "1" if use_tls else "0")
    set_secret(SOURCE_SECRET, "manual")
    return {"ok": True, "message": "Mailbox saved"}


def disconnect_institute() -> None:
    for name in (
        PROVIDER_SECRET,
        INSTITUTION_SECRET,
        EMAIL_SECRET,
        USER_SECRET,
        PASS_SECRET,
        HOST_SECRET,
        PORT_SECRET,
        SSL_SECRET,
        TLS_SECRET,
        IMAP_HOST_SECRET,
        IMAP_PORT_SECRET,
        IMAP_SSL_SECRET,
        SOURCE_SECRET,
    ):
        delete_secret(name)


def active_mail_summary() -> dict[str, Any]:
    from studio.mail.gmail import gmail_status
    from studio.mail.outlook import outlook_status

    gmail = gmail_status()
    outlook = outlook_status()
    institute = institute_status()
    if gmail["connected"]:
        kind = "gmail"
    elif outlook["connected"]:
        kind = "outlook"
    elif institute["connected"]:
        kind = "institute"
    else:
        kind = None
    return {
        "kind": kind,
        "gmail": gmail,
        "outlook": outlook,
        "institute": institute,
        "mailbox_ready": kind is not None,
    }
