"""Security controls aligned to local ASVS-style checks (INV-07/12)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException, Request

from studio.security import ALLOWED_HOSTS, is_blocked_ip, require_localhost_host, resolve_and_validate
from studio.support_bundle import build_support_bundle


def test_INV12_host_header_rejected():
    assert "evil.example" not in ALLOWED_HOSTS
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(b"host", b"evil.example")],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 80),
    }
    req = Request(scope)
    with pytest.raises(HTTPException) as ei:
        require_localhost_host(req)
    assert ei.value.status_code == 403


def test_INV12_missing_page_token_rejected(client):
    from studio.security import require_page_token

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/profile",
        "raw_path": b"/profile",
        "query_string": b"",
        "headers": [(b"host", b"127.0.0.1"), (b"cookie", b"")],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 80),
    }
    req = Request(scope)
    with pytest.raises(HTTPException) as ei:
        require_page_token(req, "forged-token")
    assert ei.value.status_code == 403


def test_INV07_ssrf_blocks_metadata_and_loopback():
    assert is_blocked_ip("127.0.0.1")
    assert is_blocked_ip("169.254.169.254")
    assert is_blocked_ip("10.0.0.1")
    with pytest.raises(ValueError):
        resolve_and_validate("http://127.0.0.1/admin")
    with pytest.raises(ValueError):
        resolve_and_validate("file:///etc/passwd")


def test_INV07_support_bundle_redacts_secrets():
    payload = {
        "smtp_password": "super-secret-password-xyz",
        "gmail_refresh_token": "refresh-token-should-not-leak",
        "email": "student@university.edu",
        "note": "ok",
    }
    raw = build_support_bundle(payload)
    assert "super-secret-password-xyz" not in raw
    assert "refresh-token-should-not-leak" not in raw
    assert "student@university.edu" not in raw
    assert "[REDACTED" in raw


def test_INV12_oauth_state_mismatch_rejected(client):
    r = client.get(
        "/mail/callback/gmail?code=forged&state=forged",
        follow_redirects=False,
    )
    assert r.status_code in (303, 302, 400, 403)
    loc = (r.headers.get("location") or "").lower()
    body = (r.text or "").lower()
    assert "err" in loc or "fail" in loc or "error" in body or r.status_code in (400, 403)
