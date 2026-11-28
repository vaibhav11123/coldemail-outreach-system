"""Gmail desktop OAuth — send-only first (sensitive scope, not restricted)."""

from __future__ import annotations

import base64
import os
import time
from email.message import EmailMessage
from typing import Any
from urllib.parse import urlencode

import requests

from studio.ai.oauth_pkce import code_challenge_s256, new_code_verifier, new_state
from studio.secrets_store import delete_secret, get_secret, set_secret

# Identity (non-sensitive) + gmail.send (sensitive). No readonly/compose/modify.
GMAIL_SEND_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.send",
]

# Separate opt-in later — restricted
GMAIL_REPLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"

CLIENT_ID_SECRET = "google_oauth_client_id"
CLIENT_SECRET_SECRET = "google_oauth_client_secret"  # optional; desktop often public+PKCE
ACCESS_SECRET = "gmail_access_token"
REFRESH_SECRET = "gmail_refresh_token"
EXPIRY_SECRET = "gmail_token_expiry"
EMAIL_SECRET = "gmail_email"
SCOPES_SECRET = "gmail_scopes"
VERIFIER_SECRET = "gmail_pkce_verifier"
STATE_SECRET = "gmail_oauth_state"
REPLY_CONSENT_SECRET = "gmail_reply_consent"

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


def client_id_configured() -> bool:
    return bool(get_secret(CLIENT_ID_SECRET) or os.environ.get("GOOGLE_OAUTH_CLIENT_ID"))


def _client_id() -> str:
    return get_secret(CLIENT_ID_SECRET) or os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or ""


def _client_secret() -> str | None:
    return get_secret(CLIENT_SECRET_SECRET) or os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")


def gmail_status() -> dict[str, Any]:
    email = get_secret(EMAIL_SECRET)
    connected = bool(get_secret(REFRESH_SECRET) or get_secret(ACCESS_SECRET))
    reply = get_secret(REPLY_CONSENT_SECRET) == "1"
    return {
        "connected": connected,
        "email": email or "",
        "permissions": "Send only",
        "permissions_detail": "Send personalized research emails from your account.",
        "features": [
            "Send personalized research emails",
            "Attach CV and research portfolio (when files are attached to the draft)",
            "Maintain sent-email history in this app",
            "Prepare follow-up reminders",
        ],
        "reply_detection": reply,
        "reply_detail": (
            "Enabled — requires gmail.readonly (restricted scope)."
            if reply
            else "Off — requires additional inbox permission (restricted). Opt in separately."
        ),
        "client_configured": client_id_configured(),
        "verification_note": (
            "Public distribution needs Google OAuth verification for gmail.send. "
            "Testing mode is limited to 100 users and 7-day refresh tokens."
        ),
    }


def start_gmail_oauth(callback_base: str) -> dict[str, Any]:
    cid = _client_id()
    if not cid:
        return {
            "ok": False,
            "message": (
                "Add a Google Desktop OAuth client id once (Advanced → Google client id). "
                "Students never create Cloud projects — only you register the app."
            ),
            "redirect_url": "https://console.cloud.google.com/apis/credentials",
        }
    verifier = new_code_verifier()
    challenge = code_challenge_s256(verifier)
    state = new_state()
    set_secret(VERIFIER_SECRET, verifier)
    set_secret(STATE_SECRET, state)
    redirect_uri = f"{callback_base.rstrip('/')}/mail/callback/gmail"
    set_secret("gmail_redirect_uri", redirect_uri)
    params = {
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GMAIL_SEND_SCOPES),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    return {
        "ok": True,
        "message": "Continue with Google in your browser.",
        "redirect_url": f"{AUTH_URL}?{urlencode(params)}",
    }


def finish_gmail_oauth(code: str, state: str = "") -> dict[str, Any]:
    code = (code or "").strip()
    if not code:
        return {"ok": False, "message": "Missing authorization code."}
    expected = get_secret(STATE_SECRET)
    if expected and state and state != expected:
        return {"ok": False, "message": "OAuth state mismatch. Try Connect Gmail again."}
    verifier = get_secret(VERIFIER_SECRET)
    if not verifier:
        return {"ok": False, "message": "Authorization expired. Start Connect Gmail again."}
    redirect_uri = get_secret("gmail_redirect_uri") or ""
    data = {
        "client_id": _client_id(),
        "code": code,
        "code_verifier": verifier,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    secret = _client_secret()
    if secret:
        data["client_secret"] = secret
    try:
        resp = requests.post(TOKEN_URL, data=data, timeout=30)
    except requests.RequestException as exc:
        return {"ok": False, "message": f"Network error: {exc}"}
    if resp.status_code >= 400:
        return {
            "ok": False,
            "message": f"Google refused the code ({resp.status_code}). Check client id and redirect URI.",
        }
    payload = resp.json()
    access = payload.get("access_token")
    if not access:
        return {"ok": False, "message": "No access token returned."}
    set_secret(ACCESS_SECRET, access)
    if payload.get("refresh_token"):
        set_secret(REFRESH_SECRET, payload["refresh_token"])
    expires_in = int(payload.get("expires_in") or 3600)
    set_secret(EXPIRY_SECRET, str(int(time.time()) + expires_in - 60))
    set_secret(SCOPES_SECRET, payload.get("scope") or " ".join(GMAIL_SEND_SCOPES))
    delete_secret(VERIFIER_SECRET)
    delete_secret(STATE_SECRET)
    # identity
    try:
        ui = requests.get(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {access}"},
            timeout=20,
        )
        if ui.status_code < 400:
            email = ui.json().get("email") or ""
            if email:
                set_secret(EMAIL_SECRET, email)
    except requests.RequestException:
        pass
    return {
        "ok": True,
        "message": f"Gmail connected{(' as ' + get_secret(EMAIL_SECRET)) if get_secret(EMAIL_SECRET) else ''}.",
        "email": get_secret(EMAIL_SECRET) or "",
    }


def refresh_access_token() -> str | None:
    refresh = get_secret(REFRESH_SECRET)
    if not refresh:
        return get_secret(ACCESS_SECRET)
    expiry = get_secret(EXPIRY_SECRET)
    if expiry and expiry.isdigit() and int(expiry) > time.time() + 30:
        return get_secret(ACCESS_SECRET)
    data = {
        "client_id": _client_id(),
        "refresh_token": refresh,
        "grant_type": "refresh_token",
    }
    secret = _client_secret()
    if secret:
        data["client_secret"] = secret
    try:
        resp = requests.post(TOKEN_URL, data=data, timeout=30)
    except requests.RequestException:
        return get_secret(ACCESS_SECRET)
    if resp.status_code >= 400:
        return None
    payload = resp.json()
    access = payload.get("access_token")
    if not access:
        return None
    set_secret(ACCESS_SECRET, access)
    expires_in = int(payload.get("expires_in") or 3600)
    set_secret(EXPIRY_SECRET, str(int(time.time()) + expires_in - 60))
    return access


def disconnect_gmail() -> None:
    for name in (
        ACCESS_SECRET,
        REFRESH_SECRET,
        EXPIRY_SECRET,
        EMAIL_SECRET,
        SCOPES_SECRET,
        VERIFIER_SECRET,
        STATE_SECRET,
        "gmail_redirect_uri",
        REPLY_CONSENT_SECRET,
    ):
        delete_secret(name)


def _mime_raw(sender: str, recipient: str, subject: str, body: str, attachments: list[tuple[str, bytes]] | None = None) -> str:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)
    for filename, data in attachments or []:
        msg.add_attachment(
            data,
            maintype="application",
            subtype="octet-stream",
            filename=filename,
        )
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii").rstrip("=")
    return raw


def send_via_gmail(
    recipient: str,
    subject: str,
    body: str,
    attachments: list[tuple[str, bytes]] | None = None,
) -> dict[str, Any]:
    token = refresh_access_token()
    if not token:
        raise ValueError("Gmail session expired. Connect Gmail again.")
    sender = get_secret(EMAIL_SECRET) or "me"
    raw = _mime_raw(sender, recipient, subject, body, attachments)
    resp = requests.post(
        SEND_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"raw": raw},
        timeout=60,
    )
    if resp.status_code >= 400:
        # Surface limit-style errors without dumping tokens
        text = resp.text[:200]
        if "rateLimitExceeded" in text or "userRateLimitExceeded" in text or resp.status_code == 429:
            raise ValueError("Gmail sending limit reached. Remaining outreach stays unsent.")
        raise ValueError(f"Gmail send failed (HTTP {resp.status_code}).")
    data = resp.json()
    return {
        "provider_message_id": data.get("id"),
        "thread_id": data.get("threadId"),
    }


def set_reply_consent(enabled: bool) -> dict[str, Any]:
    """Reply detection needs a separate restricted-scope consent — not requested at connect."""
    if enabled:
        set_secret(REPLY_CONSENT_SECRET, "1")
        return {
            "ok": True,
            "message": (
                "Reply detection is marked as desired. Enabling it requires a second Google "
                "consent for gmail.readonly (restricted). That flow ships after send-only verification."
            ),
        }
    delete_secret(REPLY_CONSENT_SECRET)
    return {"ok": True, "message": "Reply detection left off."}
