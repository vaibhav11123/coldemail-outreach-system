"""Alternative architectures: handoff, bibliography, ORCID CC0, Groq managed, MCP packaging."""

from __future__ import annotations

from studio.academic.orcid_local import lookup_orcid, search_name
from studio.ai.handoff import HANDOFF_TARGETS, build_handoff_prompt, import_handoff_body
from studio.ai.mcp_server import packaging_manifest
from studio.ai.types import EvidenceBoundRequest
from studio.bibliography import parse_bibliography
from studio.connections.registry import spec_by_id


def test_registry_alternative_decisions():
    assert spec_by_id("external_handoff").production_status == "documented"
    assert spec_by_id("open_graph").production_status == "documented"
    assert spec_by_id("google_scholar").production_status == "documented"
    assert "CC0" in (spec_by_id("orcid").purpose + spec_by_id("orcid").commercial_note)
    assert spec_by_id("semanticscholar").production_status == "unavailable"
    assert "MCP" in spec_by_id("chatgpt").title or "mcp" in spec_by_id("chatgpt").purpose.lower()
    assert "extension" in spec_by_id("claude").title.lower() or "mcpb" in spec_by_id("claude").purpose.lower()
    assert spec_by_id("groq").auth_method == "guided_key"


def test_handoff_prompt_and_import_validation():
    req = EvidenceBoundRequest(
        recipient="a@b.c",
        subject="Hi",
        body="Dear X, about https://example.edu/p1. My project: kernels.",
        evidence_snippets=["kernels", "https://example.edu/p1"],
        citations=[{"applicant": "kernels", "source": "paper", "url": "https://example.edu/p1"}],
    )
    prompt = build_handoff_prompt(req)
    assert "Do not add new names" in prompt or "rephrase" in prompt.lower()
    assert "https://example.edu/p1" in prompt
    assert len(HANDOFF_TARGETS) >= 5

    bad = import_handoff_body(req, "I invented quantum underwater weaving.")
    assert bad.ok is False

    good = import_handoff_body(
        req,
        "Dear X, about https://example.edu/p1. My project: kernels.",
    )
    assert good.ok is True
    assert good.provider_id == "external_handoff"


def test_bibtex_import_parse():
    bib = """
@article{ex2024,
  title = {Scheduling Kernels},
  author = {Ada Example},
  year = {2024},
  doi = {10.1234/example}
}
"""
    out = parse_bibliography(bib, "export.bib")
    assert out["ok"] is True
    assert out["entries"][0]["title"] == "Scheduling Kernels"
    assert "10.1234/example" in out["entries"][0]["doi"]


def test_orcid_cc0_sample_lookup():
    hit = lookup_orcid("0000-0002-1825-0097")
    assert hit["ok"] is True
    assert "Carberry" in hit["name"]
    assert hit["source"] == "orcid_cc0_snapshot"
    assert search_name("Ada")


def test_mcp_packaging_channels():
    m = packaging_manifest()
    assert "chatgpt_desktop_plugin" in m["channels"]
    assert "claude_desktop_extension" in m["channels"]
    assert "vscode_copilot_mcp" in m["channels"]
    assert any(t["name"] == "save_draft" for t in m["tools"])


def test_groq_byog_without_key(client):
    from studio.ai.providers.groq import GroqProvider

    p = GroqProvider()
    st = p.get_status()
    assert st.connected is False
    assert st.auth_kind == "guided_key"
    assert "groq" in st.detail.lower() or "key" in st.detail.lower()


def test_connections_shows_handoff_and_graph(client):
    r = client.get("/connections")
    assert r.status_code == 200
    assert "Improve with your AI" in r.text
    assert "Open academic graph" in r.text
    assert "Google Scholar import" in r.text
    assert "Groq" in r.text
    assert "Connect Groq" in r.text or "Activate free AI" in r.text


def test_bibliography_upload_route(client):
    bib = b"@article{a, title={Hello Paper}, year={2020}, author={A Author}}\n"
    r = client.post(
        "/connections/bibliography",
        data={"page_token": client.page_token},
        files={"file": ("refs.bib", bib, "application/x-bibtex")},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert "Imported" in (r.headers.get("location") or "")


def test_orcid_lookup_route(client):
    r = client.post(
        "/connections/orcid",
        data={"page_token": client.page_token, "orcid": "0000-0002-1825-0097"},
    )
    assert r.status_code == 200
    assert "Carberry" in r.text or "ORCID" in r.text


def test_zotero_detect_route(client):
    r = client.post(
        "/connections/zotero-detect",
        data={"page_token": client.page_token},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert "zotero" in (r.headers.get("location") or "").lower()
