"""Microsoft Outlook / Microsoft 365 — Mail.Send scaffold (university + personal)."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlencode

from studio.ai.oauth_pkce import code_challenge_s256, new_code_verifier, new_state
from studio.secrets_store import delete_secret, get_secret, set_secret

CLIENT_ID_SECRET = "microsoft_oauth_client_id"
ACCESS_SECRET = "outlook_access_token"
REFRESH_SECRET = "outlook_refresh_token"
EMAIL_SECRET = "outlook_email"
VERIFIER_SECRET = "outlook_pkce_verifier"
STATE_SECRET = "outlook_oauth_state"

# Application permissions for sending only — not full mailbox read
SCOPES = ["openid", "email", "profile", "offline_access", "Mail.Send"]


def outlook_status() -> dict[str, Any]:
    connected = bool(get_secret(REFRESH_SECRET) or get_secret(ACCESS_SECRET))
    return {
        "connected": connected,
        "email": get_secret(EMAIL_SECRET) or "",
        "permissions": "Send only",
        "client_configured": bool(
            get_secret(CLIENT_ID_SECRET) or os.environ.get("MICROSOFT_OAUTH_CLIENT_ID")
        ),
        "detail": (
            "Connected."
            if connected
            else (
                "Continue with Microsoft uses MS identity platform + Mail.Send. "
                "Register a public desktop client once; students only sign in."
            )
        ),
    }


def start_outlook_oauth(callback_base: str) -> dict[str, Any]:
    cid = get_secret(CLIENT_ID_SECRET) or os.environ.get("MICROSOFT_OAUTH_CLIENT_ID")
    if not cid:
        return {
            "ok": False,
            "message": (
                "Add a Microsoft public client id under Advanced email settings. "
                "Students never configure Azure apps themselves."
            ),
            "redirect_url": "https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps",
        }
    verifier = new_code_verifier()
    challenge = code_challenge_s256(verifier)
    state = new_state()
    set_secret(VERIFIER_SECRET, verifier)
    set_secret(STATE_SECRET, state)
    redirect_uri = f"{callback_base.rstrip('/')}/mail/callback/outlook"
    set_secret("outlook_redirect_uri", redirect_uri)
    params = {
        "client_id": cid,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "response_mode": "query",
        "scope": " ".join(SCOPES),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    # Common tenant for personal + work/school
    url = f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?{urlencode(params)}"
    return {"ok": True, "message": "Continue with Microsoft in your browser.", "redirect_url": url}


def finish_outlook_oauth(code: str, state: str = "") -> dict[str, Any]:
    # Token exchange implemented when client id is registered; store code path for tests.
    code = (code or "").strip()
    if not code:
        return {"ok": False, "message": "Missing authorization code."}
    expected = get_secret(STATE_SECRET)
    if expected and state and state != expected:
        return {"ok": False, "message": "OAuth state mismatch."}
    # Placeholder: full token POST to login.microsoftonline.com/.../token
    set_secret(ACCESS_SECRET, f"pending:{code[:8]}")
    delete_secret(VERIFIER_SECRET)
    delete_secret(STATE_SECRET)
    return {
        "ok": True,
        "message": (
            "Microsoft authorization code received. Complete token exchange once the "
            "Azure public client id is registered for this build."
        ),
    }


def disconnect_outlook() -> None:
    for name in (
        ACCESS_SECRET,
        REFRESH_SECRET,
        EMAIL_SECRET,
        VERIFIER_SECRET,
        STATE_SECRET,
        "outlook_redirect_uri",
    ):
        delete_secret(name)
