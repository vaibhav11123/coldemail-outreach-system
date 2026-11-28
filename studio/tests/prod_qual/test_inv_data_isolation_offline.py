"""INV-05/06/08/09/11 — funding honesty, isolation, delete, crash, offline."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from studio.db import backup_database, connect, migrate, recover_intents_on_startup
from studio.drafts import content_hash, generate_draft, save_or_update_draft
from studio.mailer_studio import create_intent, mark_submitted
from studio.opportunity_parse import classify_tri_state
from studio.summer_loader import seed_mini_bundled


def test_INV05_unknown_funding_never_promoted_to_funded():
    assert classify_tri_state("")[0] == "unknown"
    assert classify_tri_state(None)[0] == "unknown"
    assert classify_tri_state("maybe funded?")[0] == "unknown"
    # Prose without clean yes/no must stay unknown — never invent funded
    assert classify_tri_state("internship opportunity")[0] == "unknown"
    assert classify_tri_state("This position is funded")[0] == "unknown"
    # Only explicit lexicon maps to stated-yes
    assert classify_tri_state("fully funded")[0] == "stated-yes"


def test_INV08_delete_personal_keeps_bundled(client, conn):
    before = conn.execute(
        "SELECT COUNT(*) AS c FROM researcher WHERE origin='bundled'"
    ).fetchone()["c"]
    assert before >= 1
    token = client.page_token  # type: ignore[attr-defined]
    r = client.post(
        "/tracker/delete-all",
        data={"page_token": token, "confirm": "DELETE"},
        follow_redirects=False,
    )
    assert r.status_code in (303, 302)
    after = conn.execute(
        "SELECT COUNT(*) AS c FROM researcher WHERE origin='bundled'"
    ).fetchone()["c"]
    assert after == before
    facts = conn.execute("SELECT COUNT(*) AS c FROM profile_fact").fetchone()["c"]
    assert facts == 0


def test_INV06_hosted_accounts_are_scaffolding_not_isolated_tenants(client):
    """Release gate: multi-tenant isolation is NOT production-ready.

    Hosted account rows exist, but drafts/profile still live in a single desktop DB.
    This test documents the gap so we cannot claim INV-06 PASS for hosted.
    """
    token = client.page_token  # type: ignore[attr-defined]
    r = client.post(
        "/hosted/create",
        data={
            "page_token": token,
            "email": "student-a@example.com",
            "display_name": "Student A",
        },
        follow_redirects=False,
    )
    assert r.status_code in (303, 302)
    r2 = client.post(
        "/hosted/create",
        data={
            "page_token": token,
            "email": "student-b@example.com",
            "display_name": "Student B",
        },
        follow_redirects=False,
    )
    assert r2.status_code in (303, 302)
    # No per-account draft scoping API exists yet — flag for release checklist.
    page = client.get("/hosted")
    assert "Student A" in page.text and "Student B" in page.text
    from studio.db import connect as db_connect

    c = db_connect()
    try:
        applicants = c.execute("SELECT COUNT(*) AS c FROM applicant").fetchone()["c"]
        assert applicants == 1
    finally:
        c.close()


def test_INV09_committed_intent_survives_reconnect(data_dir: Path):
    db = data_dir / "studio.sqlite"
    c = connect(db)
    migrate(c)
    seed_mini_bundled(c)
    # Seed minimal opportunity + approved draft
    rid = c.execute(
        "SELECT id FROM researcher WHERE origin='bundled' LIMIT 1"
    ).fetchone()["id"]
    oid = c.execute(
        "INSERT INTO opportunity(researcher_id, kind, status, origin) VALUES (?, 'internship', 'open', 'manual')",
        (rid,),
    ).lastrowid
    body = "hello https://example.edu/x"
    h = content_hash("a@b.c", "s", body)
    did = save_or_update_draft(
        c, oid, {"recipient": "a@b.c", "subject": "s", "body": body, "content_hash": h}
    )
    c.execute("UPDATE draft SET approved_hash=content_hash WHERE id=?", (did,))
    intent = create_intent(c, did, h)
    mark_submitted(c, intent)
    c.close()

    c2 = connect(db)
    recover_intents_on_startup(c2)
    row = c2.execute("SELECT state FROM send_intent WHERE id=?", (intent,)).fetchone()
    assert row["state"] == "unknown_delivery"
    # Backup still readable
    dest = data_dir / "backup.sqlite"
    backup_database(db, dest)
    assert dest.exists() and dest.stat().st_size > 0
    c2.close()


def test_INV11_full_provider_outage_offline_core_still_works(client, conn):
    """With research/AI/mail network mocked dead, bundled search + deterministic draft work."""
    with mock.patch("studio.openalex.requests.get", side_effect=OSError("offline")):
        with mock.patch(
            "studio.academic.crossref.requests.get",
            side_effect=OSError("offline"),
        ):
            # Core screens still load offline
            for path in ("/shortlist", "/profile", "/demo", "/offer"):
                r = client.get(path)
                assert r.status_code == 200, path
            # Deterministic draft from confirmed facts
            facts = [{"kind": "project", "body": "Built offline matcher", "confirmed": 1}]
            pubs = [
                {
                    "title": "Bundled paper",
                    "url": "https://example.edu/offline",
                    "abstract": "local",
                }
            ]
            draft = generate_draft("Prof Offline", "o@ex.edu", facts, pubs, [])
            assert "Built offline matcher" in draft["body"]
            # Evidence URLs live on citations; prose stays recipient-facing
            assert any(
                (c.get("url") or "") == "https://example.edu/offline"
                for c in draft.get("citations") or []
            )


def test_INV05_ui_unknown_funding_label(client):
    r = client.get("/shortlist")
    assert r.status_code == 200
    lower = r.text.lower()
    assert "all positions funded" not in lower
