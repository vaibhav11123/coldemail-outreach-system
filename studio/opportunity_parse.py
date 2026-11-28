"""Map messy opportunity cells to stated-yes / stated-no / unknown."""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse

YES_PATTERNS = [
    re.compile(r"^\s*yes\s*$", re.I),
    re.compile(r"^\s*open\s*$", re.I),
    re.compile(r"^\s*open\s*\(", re.I),
    re.compile(r"^\s*stated[- ]?yes\s*$", re.I),
    re.compile(r"^\s*eligible\s*$", re.I),
    re.compile(r"^\s*fully funded\s*$", re.I),
    re.compile(r"^\s*partially funded\s*$", re.I),
    re.compile(r"^\s*accepted?\s*$", re.I),
    re.compile(r"^\s*permitted\s*$", re.I),
]

NO_PATTERNS = [
    re.compile(r"^\s*no\s*$", re.I),
    re.compile(r"^\s*closed\s*$", re.I),
    re.compile(r"^\s*stated[- ]?no\s*$", re.I),
    re.compile(r"^\s*not eligible\s*$", re.I),
    re.compile(r"^\s*unfunded\s*$", re.I),
    re.compile(r"^\s*not permitted\s*$", re.I),
]

UNKNOWN_HINTS = (
    "unknown",
    "not published",
    "not verified",
    "not stated",
    "not addressed",
    "closed quota",
    "no new initial",
    "no verified",
    "not an exclusion",
)


def classify_tri_state(value: str | None) -> tuple[str, str | None]:
    """Return (stated-yes|stated-no|unknown, note)."""
    if value is None:
        return "unknown", None
    text = str(value).strip()
    if not text:
        return "unknown", None
    low = text.lower()
    if any(h in low for h in UNKNOWN_HINTS):
        return "unknown", text
    for pat in YES_PATTERNS:
        if pat.search(text):
            return "stated-yes", None
    for pat in NO_PATTERNS:
        if pat.search(text):
            return "stated-no", None
    # Long prose without a clean yes/no is unknown
    if len(text) > 40 or " " in text:
        return "unknown", text
    return "unknown", text


def parse_deadline(value: str | None) -> tuple[str | None, str | None]:
    """Return (iso_date_or_none, note)."""
    if value is None:
        return None, None
    text = str(value).strip()
    if not text:
        return None, None
    low = text.lower()
    if any(h in low for h in UNKNOWN_HINTS):
        return None, text
    # Only accept a single clean date
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d %B %Y", "%B %d, %Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat(), None
        except ValueError:
            continue
    # ISO-ish short date only
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1), None
    return None, text


def parse_url(value: str | None) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    text = str(value).strip()
    if not text:
        return None, None
    parsed = urlparse(text)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return text, None
    return None, text


def is_expired(deadline: str | None, today: str | None = None) -> bool:
    if not deadline:
        return False
    from datetime import date

    try:
        d = date.fromisoformat(deadline)
    except ValueError:
        return False
    ref = date.fromisoformat(today) if today else date.today()
    return d < ref
