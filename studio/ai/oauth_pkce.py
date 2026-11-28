"""PKCE helpers shared by OpenRouter, ChatGPT, Hugging Face, etc."""

from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import urlencode


def new_code_verifier() -> str:
    return secrets.token_urlsafe(32)


def code_challenge_s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def new_state() -> str:
    return secrets.token_urlsafe(16)


def openrouter_auth_url(
    callback_url: str,
    code_challenge: str,
    state: str,
    key_label: str = "Academic Outreach Studio",
) -> str:
    params = {
        "callback_url": callback_url,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
        "key_label": key_label,
    }
    return f"https://openrouter.ai/auth?{urlencode(params)}"


def openrouter_headless_auth_url(
    code_challenge: str,
    key_label: str = "Academic Outreach Studio",
) -> str:
    params = {
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "key_label": key_label,
    }
    return f"https://openrouter.ai/auth?{urlencode(params)}"
