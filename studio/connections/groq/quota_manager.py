"""Interpret Groq rate-limit / quota responses for the Connect Assistant and rewrite path."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QuotaSignal:
    kind: str  # ok | rate_limited | quota_exhausted | revoked | unavailable
    message: str


def interpret_http_status(status_code: int) -> QuotaSignal:
    if status_code == 429:
        return QuotaSignal(
            kind="rate_limited",
            message=(
                "Groq rate limit reached on your account. "
                "Wait and retry, or use Connect instant AI (OpenRouter) / built-in draft."
            ),
        )
    if status_code in (401, 403):
        return QuotaSignal(
            kind="revoked",
            message="GroqCloud rejected your key. It may have been revoked — reconnect.",
        )
    if status_code == 413:
        return QuotaSignal(
            kind="quota_exhausted",
            message="Request too large for the current Groq allowance. Shorten the draft and retry.",
        )
    if status_code >= 500:
        return QuotaSignal(
            kind="unavailable",
            message="GroqCloud is temporarily unavailable. Try again or use the built-in draft.",
        )
    if status_code >= 400:
        return QuotaSignal(
            kind="unavailable",
            message=f"Groq HTTP {status_code}",
        )
    return QuotaSignal(kind="ok", message="")


def record_rate_limit_hint() -> str:
    return (
        "Your GroqCloud free-tier limits apply to this application. "
        "We do not pool quotas or rotate accounts."
    )
