"""Customer-facing presentation for catalog / application status tokens."""

from __future__ import annotations

from datetime import date
from typing import Any

from studio.opportunity_parse import is_expired


def format_tri_state(
    value: str | None,
    *,
    kind: str = "generic",
    verified_on: str | None = None,
) -> str:
    """Map stated-yes|stated-no|unknown (and close synonyms) to human labels."""
    raw = (value or "").strip().lower()
    yes = raw in {"stated-yes", "yes", "open", "eligible"}
    no = raw in {"stated-no", "no", "closed", "not eligible"}

    if kind == "applications":
        if yes:
            if verified_on:
                return f"Applications open — source verified on {verified_on}"
            return "Applications open"
        if no:
            return "Applications closed"
        return "Application status unconfirmed"

    if kind == "funding":
        if yes:
            return "Funding mentioned — details unconfirmed"
        if no:
            return "No funding indicated"
        return "Funding unknown"

    if kind == "international":
        if yes:
            return "International applicants eligible"
        if no:
            return "International applicants restricted"
        return "International eligibility unconfirmed"

    if kind == "email_invited":
        if yes:
            return "Direct inquiries welcome"
        if no:
            return "Direct email not invited"
        return "Contact preference unconfirmed"

    if kind == "recruitment":
        if yes:
            return "Opening listed"
        if no:
            return "Not recruiting"
        return "Unconfirmed"

    # generic
    if yes:
        return "Yes (source stated)"
    if no:
        return "No (source stated)"
    if raw in {"", "—", "-", "unknown", "none"}:
        return "Unknown"
    return value or "Unknown"


def format_application_state(state: str | None) -> str:
    mapping = {
        "ready": "Ready to apply",
        "drafted": "Draft prepared",
        "preparing": "Preparing",
        "submitted_by_me": "Submitted manually",
        "in_conversation": "In conversation",
        "closed": "Closed",
        "applied": "Applied",
    }
    key = (state or "").strip().lower()
    return mapping.get(key, (state or "Unknown").replace("_", " ").title())


def effective_opportunity_status(
    *,
    status: str | None,
    deadline: str | None,
    today: str | None = None,
) -> dict[str, Any]:
    """Separate reported source status from actionable effective status."""
    expired = is_expired(deadline, today=today)
    reported = format_tri_state(status, kind="applications")
    if expired:
        return {
            "effective": "expired",
            "label": "Expired",
            "reported": reported,
            "expired": True,
            "can_prepare_opening": False,
        }
    raw = (status or "").strip().lower()
    if raw in {"stated-no", "no", "closed"}:
        return {
            "effective": "closed",
            "label": "Closed",
            "reported": reported,
            "expired": False,
            "can_prepare_opening": False,
        }
    if raw in {"stated-yes", "yes", "open"}:
        return {
            "effective": "open",
            "label": "Open",
            "reported": reported,
            "expired": False,
            "can_prepare_opening": True,
        }
    return {
        "effective": "unconfirmed",
        "label": "Unconfirmed",
        "reported": reported,
        "expired": False,
        "can_prepare_opening": True,
    }


def format_deadline(deadline: str | None, *, today: str | None = None) -> str:
    if not deadline:
        return "No deadline recorded"
    try:
        d = date.fromisoformat(deadline)
        pretty = d.strftime("%-d %b %Y") if hasattr(d, "strftime") else deadline
    except ValueError:
        pretty = deadline
    if is_expired(deadline, today=today):
        return f"{pretty} · Expired"
    return pretty


def last_verified_label(checked_at: str | None) -> str:
    if not checked_at:
        return "Last verified: unknown"
    text = str(checked_at).strip()
    # Prefer date portion when ISO datetime
    if "T" in text:
        text = text.split("T", 1)[0]
    try:
        d = date.fromisoformat(text[:10])
        return f"Last verified: {d.strftime('%-d %b %Y')}"
    except ValueError:
        return f"Last verified: {checked_at}"


def format_date(value: str | None) -> str:
    """Human date for timestamps (e.g. ``2026-11-28 08:12:00`` -> ``28 Nov 2026``)."""
    if not value:
        return "Unknown"
    text = str(value).strip().replace("T", " ")
    try:
        return date.fromisoformat(text[:10]).strftime("%-d %b %Y")
    except ValueError:
        return text


def register_template_filters(env: Any) -> None:
    env.filters["tri_state"] = format_tri_state
    env.filters["app_state"] = format_application_state
    env.filters["deadline_label"] = format_deadline
    env.filters["verified_label"] = last_verified_label
    env.filters["date_label"] = format_date
