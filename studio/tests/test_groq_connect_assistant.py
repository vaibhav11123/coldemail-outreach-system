"""Groq Connect Assistant — state machine, explicit import, local env consent."""

from __future__ import annotations

from unittest import mock

from studio.connections.groq import credential_import, keychain, onboarding
from studio.connections.groq.browser_launcher import launch_official_dashboard
from studio.connections.groq.connection_state import ConnectionPhase, get_phase
from studio.connections.groq.credential_validator import validate_api_key
from studio.connections.groq.model_discovery import pick_model


def test_modules_layout_importable():
    assert pick_model(["openai/gpt-oss-20b"]) == "openai/gpt-oss-20b"
    out = launch_official_dashboard()
    assert "console.groq.com" in out["url"]
    assert "do not automate" in out["note"].lower() or "official" in out["note"].lower()


def test_assistant_page_renders(client):
    keychain.clear_stored_key()
    r = client.get("/ai/groq")
    assert r.status_code == 200
    assert "Connect your free AI" in r.text
    assert "Connect GroqCloud" in r.text
    assert "Paste the key" in r.text
    assert "do not read Groq session cookies" in r.text.lower() or "session cookies" in r.text.lower()
    assert "Connect instant AI" in r.text or "OpenRouter" in r.text


def test_hero_points_to_assistant(client):
    r = client.get("/ai")
    assert r.status_code == 200
    assert "Connect your free AI" in r.text
    assert 'href="/ai/groq"' in r.text
    assert "Connect instant AI" in r.text
    assert "Connect GroqCloud" in r.text


def test_state_machine_paste_success(data_dir, monkeypatch):
    keychain.clear_stored_key()
    onboarding.cancel_setup()

    class Resp:
        status_code = 200

        def json(self):
            return {"data": [{"id": "openai/gpt-oss-20b"}, {"id": "other"}]}

    monkeypatch.setattr(
        "studio.connections.groq.credential_validator.requests.get",
        lambda *a, **k: Resp(),
    )
    ok, msg, view = onboarding.complete_with_pasted_key(
        "gsk_test_student_key_abcdefghijklmnopqrstuvwxyz"
    )
    assert ok is True
    assert view.connected is True
    assert get_phase() == ConnectionPhase.CONNECTED
    assert keychain.is_connected()
    keychain.clear_stored_key()


def test_invalid_key_phase(data_dir, monkeypatch):
    keychain.clear_stored_key()

    class Resp:
        status_code = 401

        def json(self):
            return {}

    monkeypatch.setattr(
        "studio.connections.groq.credential_validator.requests.get",
        lambda *a, **k: Resp(),
    )
    ok, msg, view = onboarding.complete_with_pasted_key("bad")
    assert ok is False
    assert get_phase() == ConnectionPhase.INVALID_CREDENTIAL
    assert view.connected is False


def test_local_env_requires_consent(data_dir, monkeypatch):
    keychain.clear_stored_key()
    monkeypatch.setenv("GROQ_API_KEY", "gsk_local_student_abcdefghijklmnop")
    monkeypatch.delenv("STUDIO_GROQ_API_KEY", raising=False)
    peeked = credential_import.peek_local_env_key()
    assert peeked["found"] is True
    # Decline
    ok, _msg, view = onboarding.import_local_env_key_with_consent(consented=False)
    assert ok is False
    assert not keychain.is_connected()

    class Resp:
        status_code = 200

        def json(self):
            return {"data": [{"id": "openai/gpt-oss-20b"}]}

    monkeypatch.setattr(
        "studio.connections.groq.credential_validator.requests.get",
        lambda *a, **k: Resp(),
    )
    ok2, _msg2, view2 = onboarding.import_local_env_key_with_consent(consented=True)
    assert ok2 is True
    assert view2.connected is True
    keychain.clear_stored_key()


def test_studio_groq_env_not_auto_imported(data_dir, monkeypatch):
    keychain.clear_stored_key()
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("STUDIO_GROQ_API_KEY", "gsk_product_shared_ignored")
    peeked = credential_import.peek_local_env_key()
    assert peeked["found"] is False


def test_finish_route(client, monkeypatch):
    keychain.clear_stored_key()

    class Resp:
        status_code = 200

        def json(self):
            return {"data": [{"id": "llama-3.1-8b-instant"}]}

    monkeypatch.setattr(
        "studio.connections.groq.credential_validator.requests.get",
        lambda *a, **k: Resp(),
    )
    r = client.post(
        "/ai/groq/finish",
        data={
            "page_token": client.page_token,
            "api_key": "gsk_route_test_key_abcdefghijklmnop",
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert keychain.is_connected()
    keychain.clear_stored_key()


def test_cancel_and_setup_redirect(client):
    r = client.get("/ai/setup/groq", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert "/ai/groq" in (r.headers.get("location") or "")
    r2 = client.post(
        "/ai/groq/cancel",
        data={"page_token": client.page_token},
        follow_redirects=False,
    )
    assert r2.status_code in (302, 303)


def test_validate_api_key_empty():
    result = validate_api_key("")
    assert result.ok is False
    assert result.kind == "empty"
