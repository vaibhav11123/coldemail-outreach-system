"""Localhost binding, host allowlist, page tokens, SSRF guards."""

from __future__ import annotations

import ipaddress
import secrets
import socket
from typing import Iterable
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from fastapi.responses import Response

PAGE_TOKEN_COOKIE = "studio_page_token"
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}


def new_page_token() -> str:
    return secrets.token_urlsafe(32)


def set_page_token_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=PAGE_TOKEN_COOKIE,
        value=token,
        httponly=True,
        samesite="strict",
        max_age=60 * 60 * 12,
        path="/",
    )


def require_localhost_host(request: Request) -> None:
    host = (request.headers.get("host") or "").split(":")[0].lower()
    if host not in ALLOWED_HOSTS:
        raise HTTPException(status_code=403, detail="Host not allowed")


def require_page_token(request: Request, form_token: str | None) -> None:
    cookie = request.cookies.get(PAGE_TOKEN_COOKIE)
    if not cookie or not form_token or not secrets.compare_digest(cookie, form_token):
        raise HTTPException(status_code=403, detail="Missing or invalid page token")


def is_blocked_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    return bool(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
        or str(addr) in {"169.254.169.254", "metadata.google.internal"}
    )


def resolve_and_validate(url: str) -> tuple[str, list[str]]:
    """Validate scheme and resolved addresses. Returns (normalized_url, ips)."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http and https URLs are allowed")
    if not parsed.hostname:
        raise ValueError("URL must include a hostname")
    host = parsed.hostname
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValueError(f"DNS lookup failed: {exc}") from exc
    ips = sorted({info[4][0] for info in infos})
    for ip in ips:
        if is_blocked_ip(ip):
            raise ValueError(f"Blocked destination address: {ip}")
    return url, ips


def validate_redirect_chain(urls: Iterable[str]) -> None:
    for url in urls:
        resolve_and_validate(url)
