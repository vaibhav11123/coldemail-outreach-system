"""Live checks — real network endpoints and optional Summer zip / faculty crawl.

Run:
  STUDIO_LIVE_FACULTY=1 .venv/bin/python -m pytest studio/tests -m live -v

Summer zip (1021 records) skips when the private archive is absent.
Groq/OpenRouter live key validation is skipped when those secrets are unset.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from studio.academic.crossref import lookup_doi
from studio.academic.opencitations import citations_for_doi
from studio.db import connect, migrate
from studio.faculty import collect_school, import_people
from studio.openalex import get_works_for_author
from studio.summer_loader import load_summer_zip

pytestmark = pytest.mark.live

SUMMER = Path(
    os.environ.get(
        "SUMMER_ZIP",
        str(Path.home() / "Downloads" / "Summer-2027-research-data-20261122.zip"),
    )
)

# Known OpenAlex author used in docs/examples (Jason Priem / Impactstory)
OPENALEX_AUTHOR = "A5023888391"
# Stable public Crossref target
SAMPLE_DOI = "10.1038/nature14539"
# Smaller OpenCitations payload than nature14539 (avoids multi‑MB transfers in CI)
OC_DOI = "10.1145/3292500.3330701"


def test_live_summer_zip_load(tmp_path):
    if not SUMMER.exists():
        pytest.skip(f"Summer zip not found at {SUMMER}")
    conn = connect(tmp_path / "studio.sqlite")
    migrate(conn)
    stats = load_summer_zip(conn, SUMMER)
    assert stats["researchers"] == 1021
    assert stats["historical_sends_loaded"] == 0
    unk = conn.execute(
        "SELECT COUNT(*) AS c FROM opportunity WHERE status='unknown' AND origin='bundled'"
    ).fetchone()["c"]
    assert unk > 0
    conn.close()


def test_live_openalex_works_for_author():
    """Hit the public OpenAlex API (no key required for modest traffic)."""
    out = get_works_for_author(OPENALEX_AUTHOR)
    if out.get("error") == "rate_limited":
        pytest.skip(f"OpenAlex 429 — retry after {out.get('retry_after')}")
    if not out.get("ok"):
        pytest.fail(out.get("message") or out.get("error") or str(out))
    assert out["works"]
    assert out["works"][0].get("title")
    assert out["works"][0].get("url")


def test_live_openalex_fixture_429_still_handled():
    """Regression: 429 parsing must keep working even when live API is fine."""

    class Resp:
        status_code = 429
        headers = {"Retry-After": "3"}
        text = "rate"

        def json(self):
            return {"error": "rate_limited"}

    with mock.patch("studio.openalex.requests.get", return_value=Resp()):
        out = get_works_for_author("A1")
    assert out["error"] == "rate_limited"
    assert out["retry_after"] == 3


def test_live_crossref_doi_lookup():
    result = lookup_doi(SAMPLE_DOI)
    assert result.get("ok") is True, result
    assert "nature" in (result.get("title") or "").lower() or result.get("title")
    assert result.get("url", "").startswith("https://doi.org/")


def test_live_opencitations_for_doi():
    result = citations_for_doi(OC_DOI)
    # OpenCitations may return empty citing lists for some DOIs; ok flag should be True on HTTP success
    assert result.get("ok") is True, result
    assert result.get("doi")
    assert isinstance(result.get("citing"), list)
    assert isinstance(result.get("cited"), list)


def test_live_faculty_fixture_then_optional_network(tmp_path):
    html = (Path(__file__).parent / "fixtures" / "faculty_windows1252.html").read_text(
        encoding="utf-8"
    )
    from studio.fetch_url import extract_people_from_html

    people = extract_people_from_html(html, "https://example.edu/faculty")
    assert people
    conn = connect(tmp_path / "studio.sqlite")
    migrate(conn)
    n = import_people(conn, "mit", people)
    assert n >= 1
    before = conn.execute("SELECT COUNT(*) AS c FROM researcher").fetchone()["c"]
    if os.environ.get("STUDIO_LIVE_FACULTY") != "1":
        pytest.skip("Set STUDIO_LIVE_FACULTY=1 to hit a real school URL")
    result = collect_school("mit")
    after = conn.execute("SELECT COUNT(*) AS c FROM researcher").fetchone()["c"]
    assert after >= before
    # Live MIT page may change; accept people or a named error without wiping DB
    assert result.get("people") is not None
    if result.get("error") and not result["people"]:
        pass
    else:
        assert len(result["people"]) >= 1
    conn.close()


def test_live_studio_http_routes(tmp_path, monkeypatch):
    """Exercise critical Studio HTTP surfaces against a live ASGI app."""
    monkeypatch.setenv("STUDIO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STUDIO_FORCE_LOCAL_SECRETS", "1")
    monkeypatch.setenv("STUDIO_FORCE_BOW_EMBEDDINGS", "1")
    monkeypatch.setenv("STUDIO_LICENSING_WEBHOOK_SECRET", "live-smoke-secret")
    from studio.app import create_app
    import studio.app as app_mod

    app = create_app(data_dir=tmp_path)
    token = app_mod.PAGE_TOKEN
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        client.cookies.set("studio_page_token", token)
        paths = [
            "/offer",
            "/profile",
            "/directory",
            "/directory?q=kernel",
            "/start",
            "/shortlist",
            "/ai",
            "/connections",
            "/mail",
            "/reader",
            "/api/licensing/editions",
            "/api/licensing/issuer-public",
            "/api/licensing/device",
        ]
        for path in paths:
            r = client.get(path)
            assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"

        pay = client.post(
            "/api/licensing/webhook/payment",
            json={
                "customer_id": "live_test",
                "customer_email": "live@example.com",
                "sku": "protected_dataset",
            },
            headers={"X-Studio-Webhook-Secret": "live-smoke-secret"},
        )
        assert pay.status_code == 200, pay.text
        assert pay.json().get("license_id")

        # Live OpenAlex through product client still works in-process
        works = get_works_for_author(OPENALEX_AUTHOR)
        if works.get("ok"):
            assert works["works"]


def test_live_groq_key_optional():
    """If GROQ_API_KEY is injected, validate it against Groq's models endpoint."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        pytest.skip("GROQ_API_KEY not set — skip live Groq validation")
    import requests

    resp = requests.get(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {key}"},
        timeout=30,
    )
    assert resp.status_code == 200, resp.text[:300]
    data = resp.json()
    assert data.get("data"), "expected model list"
