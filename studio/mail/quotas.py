"""Product outreach safeguards — not Google's hard ceiling."""

from __future__ import annotations

from datetime import datetime, timedelta

from studio.secrets_store import get_secret, set_secret

DEFAULT_DAILY_LIMIT = 20
MAX_FOLLOW_UPS = 1
FOLLOW_UP_DAYS_MIN = 7
FOLLOW_UP_DAYS_MAX = 10

_SEND_LOG_KEY = "mail_send_log_json"


def _parse_log() -> list[str]:
    import json

    raw = get_secret(_SEND_LOG_KEY) or "[]"
    try:
        data = json.loads(raw)
        return [str(x) for x in data] if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _save_log(entries: list[str]) -> None:
    import json

    # Keep 48h of history
    cutoff = datetime.utcnow() - timedelta(hours=48)
    kept = []
    for e in entries:
        try:
            dt = datetime.fromisoformat(e)
        except ValueError:
            continue
        if dt >= cutoff:
            kept.append(e)
    set_secret(_SEND_LOG_KEY, json.dumps(kept))


def sent_in_rolling_24h() -> int:
    now = datetime.utcnow()
    count = 0
    for e in _parse_log():
        try:
            dt = datetime.fromisoformat(e)
        except ValueError:
            continue
        if now - dt <= timedelta(hours=24):
            count += 1
    return count


def daily_limit() -> int:
    raw = get_secret("mail_daily_limit")
    if raw and raw.isdigit():
        return max(1, min(100, int(raw)))
    return DEFAULT_DAILY_LIMIT


def can_send_now() -> tuple[bool, str]:
    used = sent_in_rolling_24h()
    limit = daily_limit()
    if used >= limit:
        return False, (
            f"Daily outreach limit reached ({used}/{limit} in the last 24 hours). "
            "Try again tomorrow, or raise the limit under Advanced email settings."
        )
    return True, f"{used}/{limit} sent in the last 24 hours"


def record_send() -> None:
    entries = _parse_log()
    entries.append(datetime.utcnow().isoformat(timespec="seconds"))
    _save_log(entries)
