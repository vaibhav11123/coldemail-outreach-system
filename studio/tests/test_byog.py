"""BYOG — Bring Your Own Groq guided connection (not managed proxy, not OAuth)."""

from __future__ import annotations

from unittest import mock

from studio.ai.providers import groq as groqmod
from studio.ai.providers.groq import GroqProvider, pick_model, validate_groq_key
from studio.ai.registry import list_provider_cards
from studio.connections.registry import spec_by_id
from studio.secrets_store import get_secret


def test_registry_byog_not_managed():
    spec = spec_by_id("groq")
    assert spec.auth_method == "guided_key"
    assert "OAuth" in (spec.commercial_note or "") or "Not OAuth" in (spec.commercial_note or "")
    assert "proxy" in (spec.commercial_note or "").lower() or "shared" in (
        spec.commercial_note or ""
    ).lower()
    cards = list_provider_cards()
    assert cards[0]["id"] == "groq"
    assert cards[0]["button_label"] == "Connect Groq"
    assert cards[0]["auth_kind"] == "guided_key"


def test_activate_free_ai_screen(client):
    r = client.get("/ai")
    assert r.status_code == 200
    assert "Activate free AI" in r.text
    assert "Connect Groq" in r.text
    assert "your own free allowance" in r.text.lower() or "your allowance" in r.text.lower()
    assert "OpenRouter" in r.text
    above = r.text.split("Advanced settings")[0]
    assert 'name="api_key"' not in above
    assert "STUDIO_GROQ" not in r.text
    assert "Included AI" not in r.text


def test_groq_setup_guided_steps(client):
    r = client.get("/ai/setup/groq")
    assert r.status_code == 200
    assert "Open GroqCloud" in r.text
    assert "Paste your GroqCloud key" in r.text
    assert "not OAuth" in r.text.lower() or "Not OAuth" in r.text or "not OAuth" in r.text
    assert "Validate and connect" in r.text


def test_validate_and_connect_stores_keychain(client, monkeypatch):
    GroqProvider().disconnect()
    class Resp:
        status_code = 200

        def json(self):
            return {
                "data": [
                    {"id": "openai/gpt-oss-20b"},
                    {"id": "llama-3.1-8b-instant"},
                ]
            }

    monkeypatch.setattr(groqmod.requests, "get", lambda *a, **k: Resp())
    r = client.post(
        "/ai/finish/groq",
        data={
            "page_token": client.page_token,
            "api_key": "gsk_test_student_key_abcdefghijklmnopqrstuvwxyz",
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert get_secret(groqmod.KEY_SECRET)
    assert get_secret(groqmod.VALIDATED_SECRET) == "1"
    assert get_secret(groqmod.MODEL_SECRET) == "openai/gpt-oss-20b"
    p = GroqProvider()
    assert p.get_status().connected is True
    assert p.get_status().can_rewrite is True
    p.disconnect()


def test_invalid_key_rejected(monkeypatch):
    class Resp:
        status_code = 401

        def json(self):
            return {"error": "unauthorized"}

    monkeypatch.setattr(groqmod.requests, "get", lambda *a, **k: Resp())
    ok, msg, models = validate_groq_key("bad-key")
    assert ok is False
    assert models == []
    assert "rejected" in msg.lower()


def test_pick_model_prefers_gpt_oss():
    assert pick_model(["other", "openai/gpt-oss-20b"]) == "openai/gpt-oss-20b"


def test_rewrite_handles_429(data_dir, monkeypatch):
    from studio.ai.types import EvidenceBoundRequest
    from studio.secrets_store import set_secret

    set_secret(groqmod.KEY_SECRET, "gsk_x")
    set_secret(groqmod.VALIDATED_SECRET, "1")
    set_secret(groqmod.MODEL_SECRET, "openai/gpt-oss-20b")

    class Resp:
        status_code = 429
        text = "rate"

        def json(self):
            return {}

    monkeypatch.setattr(groqmod.requests, "post", lambda *a, **k: Resp())
    out = GroqProvider().rewrite(
        EvidenceBoundRequest(
            recipient="a@b.c",
            subject="s",
            body="body",
            evidence_snippets=["x"],
        )
    )
    assert out.ok is False
    assert "rate limit" in out.error.lower()
    GroqProvider().disconnect()


def test_no_env_shared_key_connects_student(data_dir, monkeypatch):
    """STUDIO_GROQ_API_KEY must not silently become a shared managed backend."""
    GroqProvider().disconnect()
    monkeypatch.setenv("STUDIO_GROQ_API_KEY", "gsk_product_shared_should_be_ignored")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_also_ignored")
    p = GroqProvider()
    assert p.get_status().connected is False
    start = p.connect_start("")
    assert start.needs_paste_code is True
    assert "console.groq.com" in (start.redirect_url or "")
