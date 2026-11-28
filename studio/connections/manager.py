"""Unified connection manager — status, sections, CON-* policies."""

from __future__ import annotations

from typing import Any

from studio.connections.registry import SECTION_ORDER, all_specs, spec_by_id
from studio.connections.types import ConnectionCard, ConnectionStatus
from studio.secrets_store import get_secret


def _openalex_status() -> ConnectionStatus:
    key = get_secret("openalex_api_key")
    st = get_secret("openalex_status") or ""
    email = get_secret("openalex_email") or ""
    if key and st == "active":
        return ConnectionStatus(
            connected=True,
            detail="Live research discovery enabled.",
            account_hint=email,
            can_disconnect=True,
        )
    if key and st == "pending_activation":
        return ConnectionStatus(
            connected=False,
            detail="Activation email sent — click the link, then return here.",
            account_hint=email,
            can_disconnect=True,
        )
    return ConnectionStatus(
        connected=False,
        detail="Enter your email — OpenAlex sends an activation link. No payment for the free allowance.",
    )


def _gmail_status() -> ConnectionStatus:
    from studio.mail.gmail import gmail_status

    g = gmail_status()
    return ConnectionStatus(
        connected=bool(g.get("connected")),
        detail=g.get("permissions_detail") or g.get("permissions") or "",
        account_hint=g.get("email") or "",
        can_disconnect=bool(g.get("connected")),
    )


def _outlook_status() -> ConnectionStatus:
    from studio.mail.outlook import outlook_status

    o = outlook_status()
    return ConnectionStatus(
        connected=bool(o.get("connected")),
        detail=o.get("detail") or "",
        account_hint=o.get("email") or "",
        can_disconnect=bool(o.get("connected")),
    )


def _university_status() -> ConnectionStatus:
    from studio.mail.institute import institute_status

    i = institute_status()
    return ConnectionStatus(
        connected=bool(i.get("connected")),
        detail=i.get("detail") or "",
        account_hint=i.get("email") or "",
        can_disconnect=bool(i.get("connected")),
    )


def _ai_status(provider_id: str) -> ConnectionStatus:
    from studio.ai.registry import get_provider

    # Map connection ids to AI provider ids
    map_id = {
        "openrouter": "openrouter",
        "huggingface": "huggingface",
        "ollama": "ollama",
        "chatgpt": "chatgpt",
        "claude": "claude",
        "grok": "grok",
    }.get(provider_id, provider_id)
    p = get_provider(map_id)
    if not p:
        return ConnectionStatus(connected=False, detail="Adapter not loaded.")
    st = p.get_status()
    return ConnectionStatus(
        connected=bool(st.connected),
        detail=st.detail or "",
        account_hint=getattr(st, "account_hint", "") or "",
        can_disconnect=bool(st.connected),
        disabled_reason=getattr(st, "commercial_note", "") or "",
    )


def _github_status() -> ConnectionStatus:
    login = get_secret("github_login") or ""
    if login:
        return ConnectionStatus(
            connected=True,
            detail="Public repositories imported as suggested projects (confirm on Profile).",
            account_hint=login,
            can_disconnect=True,
        )
    return ConnectionStatus(
        connected=False,
        detail="Paste a GitHub username or profile URL — public repos only, no private access.",
    )


def _orcid_status() -> ConnectionStatus:
    oid = get_secret("orcid_id") or ""
    from studio.academic.orcid_local import load_records

    n = len(load_records(limit=50))
    if oid:
        return ConnectionStatus(
            connected=True,
            detail=f"ORCID iD saved. Local CC0 snapshot loaded ({n}+ sample records).",
            account_hint=oid,
            can_disconnect=True,
        )
    return ConnectionStatus(
        connected=False,
        detail=(
            f"Look up public identities in the local CC0 ORCID snapshot ({n} sample records). "
            "Paste an iD anytime — no paid API."
        ),
    )


def _public_sources_status() -> ConnectionStatus:
    return ConnectionStatus(
        connected=True,
        detail="Crossref DOI lookup and other public metadata APIs are built-in — no login.",
        account_hint="Always on",
    )


def _calendar_status() -> ConnectionStatus:
    return ConnectionStatus(
        connected=False,
        detail="Export deadlines and follow-ups as .ics — works without OAuth.",
    )


def _local_files_status() -> ConnectionStatus:
    return ConnectionStatus(
        connected=True,
        detail="Upload CV and documents on your Profile — no external account.",
        account_hint="Device",
    )


def _faculty_status() -> ConnectionStatus:
    return ConnectionStatus(
        connected=True,
        detail="Faculty directory collection uses public pages — no login.",
    )


def _zotero_status() -> ConnectionStatus:
    from studio.zotero_local import detect_zotero

    det = detect_zotero()
    return ConnectionStatus(
        connected=bool(det.get("connected")),
        detail=det.get("message") or "",
        account_hint="local" if det.get("connected") else "",
    )


def _drive_status() -> ConnectionStatus:
    return ConnectionStatus(
        connected=False,
        detail="Google Picker + drive.file (selected files only) — incremental after Gmail.",
        disabled_reason="Adapter ready; enable after Google production verification.",
    )


def _onedrive_status() -> ConnectionStatus:
    return ConnectionStatus(
        connected=False,
        detail="Microsoft File Picker — disclose actual delegated scopes before enable.",
        disabled_reason="Adapter ready; Entra app registration required.",
    )


def _puter_status() -> ConnectionStatus:
    if get_secret("puter_connected") == "1":
        return ConnectionStatus(
            connected=True,
            detail="Puter user-pays AI authorized.",
            can_disconnect=True,
        )
    return ConnectionStatus(
        connected=False,
        detail="Sign in once; inference uses your Puter allowance (live quality TBD).",
    )


def _groq_status() -> ConnectionStatus:
    return _ai_status("groq")


def _handoff_status() -> ConnectionStatus:
    return ConnectionStatus(
        connected=False,
        detail="Available on every draft — no login. We prepare the prompt; you paste the result back for validation.",
        account_hint="",
    )


def _open_graph_status() -> ConnectionStatus:
    return ConnectionStatus(
        connected=False,
        detail="Built-in: OpenAlex + OpenCitations (CC0) + Crossref. Independent graph — not Semantic Scholar’s API.",
        account_hint="",
    )


def _scholar_status() -> ConnectionStatus:
    return ConnectionStatus(
        connected=False,
        detail="Import BibTeX/CSV exports from Google Scholar. No scraping.",
    )


def _mcp_channel_status(name: str) -> ConnectionStatus:
    return ConnectionStatus(
        connected=False,
        detail=(
            f"Reverse integration: {name} calls our local MCP tools. "
            "Subscription stays in their client."
        ),
    )


_STATUS_FN = {
    "gmail": _gmail_status,
    "outlook": _outlook_status,
    "university_mail": _university_status,
    "openrouter": lambda: _ai_status("openrouter"),
    "huggingface": lambda: _ai_status("huggingface"),
    "ollama": lambda: _ai_status("ollama"),
    "chatgpt": lambda: _mcp_channel_status("ChatGPT"),
    "claude": lambda: _mcp_channel_status("Claude"),
    "grok": lambda: ConnectionStatus(
        connected=False,
        disabled_reason="No unofficial SuperGrok OAuth.",
        detail="Use OpenRouter, Puter, or Improve with your AI.",
    ),
    "puter": _puter_status,
    "groq": _groq_status,
    "external_handoff": _handoff_status,
    "openalex": _openalex_status,
    "public_sources": _public_sources_status,
    "open_graph": _open_graph_status,
    "faculty_directories": _faculty_status,
    "semanticscholar": lambda: ConnectionStatus(
        connected=False,
        disabled_reason="Replaced by open academic graph.",
        detail="Do not use the restricted commercial API in the paid product.",
    ),
    "google_scholar": _scholar_status,
    "github": _github_status,
    "orcid": _orcid_status,
    "zotero": _zotero_status,
    "local_files": _local_files_status,
    "google_drive": _drive_status,
    "onedrive": _onedrive_status,
    "calendar": _calendar_status,
}


def status_for(cid: str) -> ConnectionStatus:
    fn = _STATUS_FN.get(cid)
    if not fn:
        return ConnectionStatus(connected=False, detail="Unknown connection.")
    return fn()


def list_connection_cards(*, include_unavailable: bool = True) -> list[ConnectionCard]:
    cards = []
    for spec in all_specs():
        if (
            not include_unavailable
            and spec.production_status in {"unavailable", "clearance_required"}
        ):
            continue
        cards.append(ConnectionCard(spec=spec, status=status_for(spec.id)))
    return cards


def sections_for_ui() -> list[dict[str, Any]]:
    cards = list_connection_cards(include_unavailable=True)
    by_section: dict[str, list[dict[str, Any]]] = {}
    for c in cards:
        by_section.setdefault(c.spec.section, []).append(c.as_dict())
    out = []
    for sid, title in SECTION_ORDER:
        out.append(
            {
                "id": sid,
                "title": title,
                "cards": by_section.get(sid, []),
            }
        )
    return out


def workspace_setup_steps() -> list[dict[str, Any]]:
    """Zero-mandatory onboarding checklist (CON-01)."""
    oa = status_for("openalex")
    ai = status_for("openrouter")
    mail = (
        status_for("gmail").connected
        or status_for("outlook").connected
        or status_for("university_mail").connected
    )
    return [
        {
            "id": "profile",
            "title": "Academic profile",
            "detail": "Upload your CV or import projects",
            "href": "/profile",
            "cta": "Create profile",
            "done": False,
        },
        {
            "id": "discovery",
            "title": "Research discovery",
            "detail": "Your included library is ready to use",
            "href": "/start",
            "cta": "Explore",
            "done": True,
        },
        {
            "id": "ai",
            "title": "AI writing assistant",
            "detail": "Connect free AI or continue with built-in drafts",
            "href": "/ai",
            "cta": "Activate AI",
            "done": ai.connected,
        },
        {
            "id": "email",
            "title": "Your email",
            "detail": "Personal or university email",
            "href": "/mail",
            "cta": "Connect email",
            "done": mail,
        },
        {
            "id": "openalex",
            "title": "Live research search",
            "detail": "Optional OpenAlex activation",
            "href": "/connections#openalex",
            "cta": "Activate",
            "done": oa.connected,
        },
        {
            "id": "documents",
            "title": "Documents and calendar",
            "detail": "Keep applications organized",
            "href": "/connections#calendar",
            "cta": "Set up",
            "done": False,
        },
    ]


def prefill_email_candidates() -> list[str]:
    """Emails from connected mail — for OpenAlex prefill with permission."""
    out = []
    for cid in ("gmail", "university_mail", "outlook"):
        hint = status_for(cid).account_hint
        if hint and "@" in hint and hint not in out:
            out.append(hint)
    saved = get_secret("openalex_email")
    if saved and saved not in out:
        out.insert(0, saved)
    return out


def connection_requirements() -> list[dict[str, str]]:
    """CON-01 … CON-18 as machine-readable checklist."""
    return [
        {"id": "CON-01", "text": "No mandatory external account for core functionality"},
        {"id": "CON-02", "text": "No manual API key for the standard customer workflow"},
        {"id": "CON-03", "text": "Automatic OAuth / credential acquisition where supported"},
        {"id": "CON-04", "text": "Incremental, feature-specific permissions"},
        {"id": "CON-05", "text": "Automatic credential renewal"},
        {"id": "CON-06", "text": "Provider-specific quota monitoring"},
        {"id": "CON-07", "text": "Automatic institutional email configuration discovery"},
        {"id": "CON-08", "text": "Separate desktop vs hosted credential storage"},
        {"id": "CON-09", "text": "Disconnect and revoke where supported"},
        {"id": "CON-10", "text": "No cross-account credential or data sharing"},
        {"id": "CON-11", "text": "No silent paid inference fallback"},
        {"id": "CON-12", "text": "Privacy disclosure before external data transfer"},
        {"id": "CON-13", "text": "Commercial licensing registry for APIs and models"},
        {"id": "CON-14", "text": "Disabled integrations explain availability"},
        {"id": "CON-15", "text": "Deterministic / manual fallbacks for essential workflows"},
        {"id": "CON-16", "text": "Live authentication and revocation acceptance tests"},
        {"id": "CON-17", "text": "No undocumented subscription bridges"},
        {"id": "CON-18", "text": "No customer-facing developer configuration in normal onboarding"},
    ]


def get_spec(cid: str):
    return spec_by_id(cid)
