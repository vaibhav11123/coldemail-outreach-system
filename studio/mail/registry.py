"""Verified university mail configs from official computer-centre docs.

Students never enter host/port themselves when their domain matches.
Only include entries with a published source; expand carefully.
"""

from __future__ import annotations

from studio.mail.types import ServerEndpoint

# Domain suffix → config. Longest-suffix match wins (dept.iitd.ac.in → iitd.ac.in).
UNIVERSITY_REGISTRY: dict[str, dict] = {
    "iitd.ac.in": {
        "institution": "IIT Delhi",
        "auth_method": "password",
        "confidence": "verified",
        "source_url": "https://csc.iitd.ac.in/services-network-email-client-config",
        "detail": "Institutional mail configuration detected (IIT Delhi CSC).",
        "smtp": ServerEndpoint(
            host="smtp.iitd.ac.in",
            port=465,
            security="ssl",
            username_template="%EMAILLOCALPART%",
        ),
        "imap": ServerEndpoint(
            host="mailstore.iitd.ac.in",
            port=993,
            security="ssl",
            username_template="%EMAILLOCALPART%",
        ),
        "notes": [
            "Official client settings match Thunderbird/Outlook/Apple Mail.",
            "Outgoing mail requires institute login authentication.",
        ],
    },
    "iitm.ac.in": {
        "institution": "IIT Madras",
        "auth_method": "password",
        "confidence": "verified",
        "source_url": "https://cc.iitm.ac.in/eservices/emailonzimbraserver.html",
        "detail": "Institutional Zimbra mail configuration detected (IIT Madras).",
        "smtp": ServerEndpoint(
            host="smtp.iitm.ac.in",
            port=465,
            security="ssl",
            username_template="%EMAILLOCALPART%",
        ),
        "imap": ServerEndpoint(
            host="web.zmail.iitm.ac.in",
            port=993,
            security="ssl",
            username_template="%EMAILLOCALPART%",
        ),
        "notes": [
            "Use LDAP username/password (no trailing digit quirks in client).",
            "Alternate outbound host smtp2.iitm.ac.in is also published.",
        ],
    },
    "zmail.iitm.ac.in": {
        "institution": "IIT Madras",
        "auth_method": "password",
        "confidence": "verified",
        "source_url": "https://cc.iitm.ac.in/eservices/emailonzimbraserver.html",
        "detail": "Institutional Zimbra mail configuration detected (IIT Madras).",
        "smtp": ServerEndpoint(
            host="smtp.iitm.ac.in",
            port=465,
            security="ssl",
            username_template="%EMAILLOCALPART%",
        ),
        "imap": ServerEndpoint(
            host="web.zmail.iitm.ac.in",
            port=993,
            security="ssl",
            username_template="%EMAILLOCALPART%",
        ),
        "notes": ["Zimbra address form of IIT Madras mail."],
    },
    "iitk.ac.in": {
        "institution": "IIT Kanpur",
        "auth_method": "password",
        "confidence": "verified",
        "source_url": "https://iitk.ac.in/nt/faq/outlook.htm",
        "detail": "Institutional mail configuration detected (IIT Kanpur, external network).",
        "smtp": ServerEndpoint(
            host="mmtp.iitk.ac.in",
            port=465,
            security="ssl",
            username_template="%EMAILLOCALPART%",
        ),
        "imap": ServerEndpoint(
            host="qasid.iitk.ac.in",
            port=993,
            security="ssl",
            username_template="%EMAILLOCALPART%",
        ),
        "notes": [
            "External-network hosts (laptops/mobiles). Campus-only hosts differ.",
        ],
    },
    # Consumer / Workspace shortcuts (auth via OAuth, not password SMTP)
    "gmail.com": {
        "institution": "Gmail",
        "auth_method": "oauth_google",
        "confidence": "verified",
        "source_url": "https://autoconfig.thunderbird.net/v1.1/gmail.com",
        "detail": "Google account detected — Continue with Google (no password in this app).",
        "smtp": None,
        "imap": None,
        "notes": [],
    },
    "googlemail.com": {
        "institution": "Gmail",
        "auth_method": "oauth_google",
        "confidence": "verified",
        "source_url": "https://autoconfig.thunderbird.net/v1.1/gmail.com",
        "detail": "Google account detected — Continue with Google.",
        "smtp": None,
        "imap": None,
        "notes": [],
    },
    "outlook.com": {
        "institution": "Microsoft Outlook",
        "auth_method": "oauth_microsoft",
        "confidence": "verified",
        "source_url": "",
        "detail": "Microsoft account detected — Continue with Microsoft.",
        "smtp": None,
        "imap": None,
        "notes": [],
    },
    "hotmail.com": {
        "institution": "Microsoft Outlook",
        "auth_method": "oauth_microsoft",
        "confidence": "verified",
        "source_url": "",
        "detail": "Microsoft account detected — Continue with Microsoft.",
        "smtp": None,
        "imap": None,
        "notes": [],
    },
    "live.com": {
        "institution": "Microsoft Outlook",
        "auth_method": "oauth_microsoft",
        "confidence": "verified",
        "source_url": "",
        "detail": "Microsoft account detected — Continue with Microsoft.",
        "smtp": None,
        "imap": None,
        "notes": [],
    },
}


def lookup_domain(domain: str) -> tuple[str, dict] | None:
    """Longest-suffix match against the verified registry."""
    domain = (domain or "").lower().strip().rstrip(".")
    if not domain:
        return None
    if domain in UNIVERSITY_REGISTRY:
        return domain, UNIVERSITY_REGISTRY[domain]
    parts = domain.split(".")
    for i in range(1, len(parts)):
        suffix = ".".join(parts[i:])
        if suffix in UNIVERSITY_REGISTRY:
            return suffix, UNIVERSITY_REGISTRY[suffix]
    return None
