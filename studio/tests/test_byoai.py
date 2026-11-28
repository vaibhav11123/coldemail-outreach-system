"""BYOAI: provider registry, OpenRouter PKCE helpers, evidence validation, Connect AI screen."""

from __future__ import annotations

from unittest import mock

from studio.ai.engine import rewrite_draft, validate_rewrite
from studio.ai.oauth_pkce import code_challenge_s256, new_code_verifier, openrouter_auth_url
from studio.ai.registry import list_provider_cards, set_active_provider
from studio.ai.types import EvidenceBoundRequest
from studio.secrets_store import set_secret


def test_pkce_challenge_stable_shape():
    v = new_code_verifier()
    c = code_challenge_s256(v)
    assert len(c) >= 40
    assert "=" not in c
    url = openrouter_auth_url("http://127.0.0.1:8765/ai/callback/openrouter", c, "st")
    assert "openrouter.ai/auth" in url
    assert "code_challenge_method=S256" in url
    assert "callback_url=" in url


def test_provider_cards_include_free_ai_first():
    cards = list_provider_cards()
    assert cards[0]["id"] == "openrouter"
    assert cards[0]["recommended"] is True
    ids = {c["id"] for c in cards}
    assert {"openrouter", "chatgpt", "copilot", "gemini", "ollama", "claude", "custom", "grok"} <= ids


def test_connect_ai_screen(client):
    r = client.get("/ai")
    assert r.status_code == 200
    assert "Connect your AI" in r.text
    assert "Connect free AI" in r.text
    assert "Continue without AI" in r.text
    assert "Advanced settings" in r.text
    above = r.text.split("Advanced settings")[0]
    # Student paste/key fields stay under Advanced — managed copy may say "no student account"
    assert 'name="api_key"' not in above
    assert "Paste your" not in above


def test_continue_without_ai(client):
    r = client.post(
        "/ai/continue-without",
        data={"page_token": client.page_token},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)


def test_openrouter_finish_stores_key(client, monkeypatch):
    from studio.ai.providers import openrouter as ormod

    set_secret(ormod.VERIFIER_SECRET, "verifier-test")

    class Resp:
        status_code = 200
        content = b'{"key":"sk-or-v1-testdemo1234","user_id":"user_x"}'

        def json(self):
            return {"key": "sk-or-v1-testdemo1234", "user_id": "user_x"}

    monkeypatch.setattr(ormod.requests, "post", lambda *a, **k: Resp())
    r = client.post(
        "/ai/finish/openrouter",
        data={"page_token": client.page_token, "code": "auth_code"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    cards = list_provider_cards()
    or_card = next(c for c in cards if c["id"] == "openrouter")
    assert or_card["status"].connected is True


def test_ollama_detect_when_absent(client):
    r = client.post(
        "/ai/connect/ollama",
        data={"page_token": client.page_token},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "Ollama" in r.text or "Local" in r.text or "127.0.0.1" in r.text or "not" in r.text.lower()


def test_validate_rewrite_rejects_new_claim():
    req = EvidenceBoundRequest(
        recipient="a@b.c",
        subject="Hi",
        body="Dear X, about https://example.edu/p1. My project: kernels.",
        evidence_snippets=["kernels", "https://example.edu/p1", "scheduling"],
        citations=[{"applicant": "kernels", "source": "scheduling", "url": "https://example.edu/p1"}],
    )
    ok, notes = validate_rewrite(
        req, "Hi", "I researched quantum underwater basket weaving extensively."
    )
    assert ok is False
    assert notes


def test_rewrite_falls_back_without_provider():
    req = EvidenceBoundRequest(
        recipient="a@b.c",
        subject="Hi",
        body="Existing letter body with https://example.edu/p1",
        evidence_snippets=["https://example.edu/p1", "kernels"],
    )
    result = rewrite_draft(req)
    assert result.ok
    assert result.used_deterministic_fallback or result.provider_id == "deterministic"


def test_mcp_tool_list():
    from studio.ai.mcp_server import list_tools

    names = {t["name"] for t in list_tools()}
    assert "generate_evidence_bound_draft" in names
    assert "validate_draft" in names


def test_engine_rejects_provider_invention(monkeypatch):
    class Fake:
        id = "fake"

        def get_status(self):
            from studio.ai.types import ProviderStatus

            return ProviderStatus(
                id="fake", connected=True, label="Fake", can_rewrite=True
            )

        def rewrite(self, request):
            from studio.ai.types import RewriteResult

            return RewriteResult(
                ok=True,
                subject=request.subject,
                body="I discovered a brand new theorem on lunar agriculture.",
                provider_id="fake",
                model="x",
            )

    monkeypatch.setattr("studio.ai.engine.get_active_provider", lambda: Fake())
    req = EvidenceBoundRequest(
        recipient="a@b.c",
        subject="Hi",
        body="About https://example.edu/p1 and kernels.",
        evidence_snippets=["https://example.edu/p1", "kernels"],
        citations=[{"applicant": "kernels", "source": "paper", "url": "https://example.edu/p1"}],
    )
    result = rewrite_draft(req)
    assert result.used_deterministic_fallback
    assert result.rejected_claims or result.error
