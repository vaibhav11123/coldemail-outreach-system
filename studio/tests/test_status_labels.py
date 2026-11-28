"""Customer-facing status wording and effective opportunity status."""

from __future__ import annotations

import pytest

from studio.status_labels import effective_opportunity_status, format_tri_state


@pytest.mark.parametrize(
    "value,kind,expected",
    [
        ("stated-yes", "applications", "Applications open"),
        ("stated-no", "applications", "Applications closed"),
        ("unknown", "applications", "Application status unconfirmed"),
        (None, "applications", "Application status unconfirmed"),
        ("stated-yes", "funding", "Funding mentioned — details unconfirmed"),
        ("stated-no", "funding", "No funding indicated"),
        ("unknown", "funding", "Funding unknown"),
        ("stated-yes", "international", "International applicants eligible"),
        ("unknown", "international", "International eligibility unconfirmed"),
        ("stated-yes", "email_invited", "Direct inquiries welcome"),
        ("unknown", "email_invited", "Contact preference unconfirmed"),
        ("stated-yes", "generic", "Yes (source stated)"),
        ("", "generic", "Unknown"),
    ],
)
def test_format_tri_state(value, kind, expected):
    assert format_tri_state(value, kind=kind) == expected


def test_format_tri_state_never_leaks_raw_token():
    for kind in ("applications", "funding", "international", "email_invited", "recruitment", "generic"):
        for token in ("stated-yes", "stated-no", "unknown"):
            assert "stated-" not in format_tri_state(token, kind=kind)


def test_format_tri_state_applications_verified_date():
    assert (
        format_tri_state("stated-yes", kind="applications", verified_on="3 Mar 2026")
        == "Applications open — source verified on 3 Mar 2026"
    )


def test_effective_status_expired_overrides_reported_open():
    out = effective_opportunity_status(status="stated-yes", deadline="2020-01-01", today="2026-06-01")
    assert out["effective"] == "expired"
    assert out["expired"] is True
    assert out["can_prepare_opening"] is False
    assert out["reported"] == "Applications open"


def test_effective_status_open_closed_unconfirmed():
    kw = {"deadline": "2099-01-01", "today": "2026-06-01"}
    assert effective_opportunity_status(status="stated-yes", **kw)["effective"] == "open"
    assert effective_opportunity_status(status="stated-yes", **kw)["can_prepare_opening"] is True
    closed = effective_opportunity_status(status="stated-no", **kw)
    assert closed["effective"] == "closed" and closed["can_prepare_opening"] is False
    unk = effective_opportunity_status(status="unknown", deadline=None, today="2026-06-01")
    assert unk["effective"] == "unconfirmed" and unk["can_prepare_opening"] is True
