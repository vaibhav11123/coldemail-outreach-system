"""Unified Connections registry, OpenAlex UX, GitHub import, Crossref, .ics."""

from __future__ import annotations

from unittest import mock

from studio.academic.crossref import lookup_doi, normalize_doi
from studio.calendar_export import build_ics
from studio.connections import (
    connection_requirements,
    list_connection_cards,
    sections_for_ui,
    workspace_setup_steps,
)
from studio.connections.registry import spec_by_id
from studio.github_import import parse_github_login


def test_connection_registry_has_p0_core():
    ids = {c.spec.id for c in list_connection_cards()}
    for required in (
        "gmail",
        "outlook",
        "university_mail",
        "openrouter",
        "openalex",
        "public_sources",
        "github",
        "calendar",
        "local_files",
    ):
        assert required in ids
    # CON-01: nothing required
    assert all(not c.spec.required for c in list_connection_cards())


def test_con_requirements_eighteen():
    reqs = connection_requirements()
    assert len(reqs) == 18
    assert reqs[0]["id"] == "CON-01"


def test_clearance_providers_explain_disabled():
    ss = spec_by_id("semanticscholar")
    assert ss is not None
    assert ss.production_status == "clearance_required"
    grok = spec_by_id("grok")
    assert grok is not None
    assert grok.production_status == "unavailable"


def test_connections_screen(client):
    r = client.get("/connections")
    assert r.status_code == 200
    assert "Connections" in r.text
    assert "Every connection is optional" in r.text
    assert "Activate research search" in r.text or "OpenAlex" in r.text
    assert "Gmail" in r.text
    assert "University email" in r.text
    assert "Free AI" in r.text
    assert "GitHub" in r.text
    assert "CON-01" in r.text
    assert "No developer accounts or API keys required" in r.text


def test_workspace_setup_steps_discovery_ready():
    steps = workspace_setup_steps()
    disc = next(s for s in steps if s["id"] == "discovery")
    assert disc["done"] is True


def test_sections_order():
    sections = sections_for_ui()
    assert [s["id"] for s in sections] == [
        "email",
        "ai",
        "research",
        "profile",
        "documents",
    ]


def test_parse_github_login():
    assert parse_github_login("https://github.com/octocat") == "octocat"
    assert parse_github_login("@octocat") == "octocat"
    assert parse_github_login("bad user!") is None


def test_github_import_posts_facts(client, monkeypatch):
    repos = {
        "ok": True,
        "login": "octocat",
        "repos": [
            {
                "name": "Hello-World",
                "url": "https://github.com/octocat/Hello-World",
                "description": "Demo",
                "language": "Python",
                "topics": ["demo"],
                "suggested_body": "Hello-World — Demo (Python, demo) https://github.com/octocat/Hello-World",
            }
        ],
    }
    monkeypatch.setattr("studio.app.fetch_public_repos", lambda *a, **k: repos)
    r = client.post(
        "/connections/github",
        data={"page_token": client.page_token, "github": "octocat"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert "Imported" in (r.headers.get("location") or "")
    # Verify via app DB
    from studio import db as dbmod

    conn = dbmod.connect()
    try:
        row = conn.execute(
            "SELECT confirmed, source, body FROM profile_fact WHERE source='github'"
        ).fetchone()
        assert row is not None
        assert row["confirmed"] == 0
        assert "Hello-World" in row["body"]
    finally:
        conn.close()


def test_crossref_normalize_and_lookup(monkeypatch):
    assert normalize_doi("https://doi.org/10.1038/nature14539") == "10.1038/nature14539"

    class Resp:
        status_code = 200

        def json(self):
            return {
                "message": {
                    "title": ["Example Paper"],
                    "issued": {"date-parts": [[2015, 1, 1]]},
                    "author": [{"given": "A", "family": "Author"}],
                    "container-title": ["Nature"],
                }
            }

    monkeypatch.setattr(
        "studio.academic.crossref.requests.get", lambda *a, **k: Resp()
    )
    out = lookup_doi("10.1038/nature14539")
    assert out["ok"] is True
    assert out["title"] == "Example Paper"
    assert "internship" in out["note"].lower() or "not" in out["note"].lower()


def test_crossref_route(client, monkeypatch):
    monkeypatch.setattr(
        "studio.app.lookup_doi",
        lambda doi: {
            "ok": True,
            "doi": "10.1/x",
            "title": "T",
            "year": 2020,
            "authors": ["A"],
            "url": "https://doi.org/10.1/x",
            "note": "Publication metadata is evidence of research activity, not of an open internship.",
        },
    )
    r = client.post(
        "/connections/crossref",
        data={"page_token": client.page_token, "doi": "10.1/x"},
    )
    assert r.status_code == 200
    assert "evidence of research" in r.text.lower() or "T" in r.text


def test_calendar_ics(client):
    r = client.get("/connections/calendar.ics")
    assert r.status_code == 200
    assert "text/calendar" in r.headers.get("content-type", "")
    assert "BEGIN:VCALENDAR" in r.text
    assert "VEVENT" in r.text


def test_ics_builder_escapes():
    body = build_ics(
        [{"summary": "A;B", "description": "line1\nline2", "start": __import__("datetime").datetime(2026, 12, 5, 9)}]
    )
    assert "A\\;B" in body


def test_openalex_activation_copy_on_connections(client, monkeypatch):
    monkeypatch.setattr(
        "studio.app.request_api_key",
        lambda email: {"http_status": 201, "api_key": "k", "status": "pending_activation"},
    )
    # also patch module used if re-imported
    monkeypatch.setattr(
        "studio.openalex.request_api_key",
        lambda email: {"http_status": 201, "api_key": "k", "status": "pending_activation"},
    )
    r = client.post(
        "/openalex/connect",
        data={"page_token": client.page_token, "email": "student@uni.edu"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    loc = r.headers.get("location") or ""
    assert "/connections" in loc
    assert "activation" in loc.lower() or "OpenAlex" in loc


def test_offer_mentions_optional_connections(client):
    r = client.get("/offer")
    assert "Set up connections" in r.text
    assert "No mandatory external accounts" in r.text


def test_nav_has_connections(client):
    r = client.get("/offer")
    assert 'href="/connections"' in r.text
