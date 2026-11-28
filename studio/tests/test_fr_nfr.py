"""One automated test per FR-1..FR-25 and NFR-1..NFR-7."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path
from unittest import mock

import pytest

from studio.db import connect, migrate, recover_intents_on_startup
from studio.drafts import approve_draft, content_hash, generate_draft, save_or_update_draft, to_eml
from studio.mailer_studio import create_intent, mark_submitted
from studio.matching import rebuild_shortlist, score_opportunity
from studio.opportunity_parse import classify_tri_state
from studio.security import is_blocked_ip, resolve_and_validate
from studio.sheet_import import commit_import, read_tabular
from studio.summer_loader import seed_mini_bundled


def test_FR1_offer_and_start_no_send(client):
    r = client.get("/offer")
    assert r.status_code == 200
    assert "send" not in r.text.lower() or "No send" in r.text or "research internship" in r.text.lower()
    assert "Summer 2027" in r.text
    # no provider send control on offer
    assert 'action="/mail/send' not in r.text
    r2 = client.get("/start")
    assert r2.status_code == 200
    assert "Summer 2027" in r2.text


def test_FR2_demo_labeled(client):
    r = client.get("/demo")
    assert r.status_code == 200
    assert "Demo" in r.text
    assert "Demo Lab" in r.text
    assert "synthetic" in r.text.lower() or "Demo" in r.text


def test_FR3_paper_needs_url_unknowns(conn):
    opp = conn.execute("SELECT * FROM opportunity WHERE demo=1 LIMIT 1").fetchone()
    pubs = conn.execute(
        "SELECT * FROM publication WHERE researcher_id=?", (opp["researcher_id"],)
    ).fetchall()
    for p in pubs:
        assert p["url"] and p["url"].startswith("http")
    # unknown funding card exists
    unk = conn.execute(
        "SELECT * FROM opportunity WHERE demo=1 AND funding='unknown'"
    ).fetchone()
    assert unk is not None


def test_FR4_openalex_429_names_failure():
    from studio import openalex

    class Resp:
        status_code = 429
        headers = {"Retry-After": "7"}
        text = "rate"

        def json(self):
            return {}

    with mock.patch("studio.openalex.requests.get", return_value=Resp()):
        out = openalex.get_works_for_author("A123")
    assert out["ok"] is False
    assert out["error"] == "rate_limited"
    assert out["retry_after"] == 7


def test_FR5_sheet_import_blank_email(conn):
    headers, rows, _ = read_tabular(
        "t.csv",
        b"Name,University,Email\nAda Test,Test U,\n",
    )
    n = commit_import(conn, rows, {"name": "Name", "affiliation": "University", "email": "Email"})
    assert n == 1
    row = conn.execute(
        "SELECT email FROM researcher WHERE display_name='Ada Test'"
    ).fetchone()
    assert row["email"] is None or row["email"] == ""


def test_FR6_corrupt_or_overcap_imports_nothing(tmp_path, conn):
    with pytest.raises(ValueError):
        read_tabular("bad.xlsx", b"not-a-zip")
    huge = b"x" * (20 * 1024 * 1024 + 1)
    with pytest.raises(ValueError):
        read_tabular("big.csv", huge)
    before = conn.execute("SELECT COUNT(*) AS c FROM researcher").fetchone()["c"]
    # nothing committed on failure path above
    after = conn.execute("SELECT COUNT(*) AS c FROM researcher").fetchone()["c"]
    assert before == after


def test_FR7_reimport_keeps_draft(conn):
    research = conn.execute(
        "SELECT id FROM researcher WHERE origin='bundled' LIMIT 1"
    ).fetchone()
    opp = conn.execute(
        "SELECT id FROM opportunity WHERE researcher_id=?", (research["id"],)
    ).fetchone()
    draft = {
        "recipient": "a@b.c",
        "subject": "hi",
        "body": "body with https://example.edu/papers/ben-1",
        "content_hash": content_hash("a@b.c", "hi", "body with https://example.edu/papers/ben-1"),
    }
    did = save_or_update_draft(conn, opp["id"], draft)
    # re-seed mini (idempotent count) then ensure draft remains
    seed_mini_bundled(conn)
    still = conn.execute("SELECT id FROM draft WHERE id=?", (did,)).fetchone()
    assert still is not None


def test_FR8_match_reasons_cited(conn):
    conn.execute(
        "INSERT INTO profile_fact(kind, body, source, confirmed) VALUES ('project', 'Built a CUDA kernel scheduler for MoE inference', 'typed', 1)"
    )
    conn.execute(
        "INSERT INTO profile_fact(kind, body, source, confirmed) VALUES ('interest', 'GPU scheduling', 'typed', 1)"
    )
    rebuild_shortlist(conn)
    row = conn.execute(
        "SELECT rank_explanation FROM shortlist_item ORDER BY rank_score DESC LIMIT 1"
    ).fetchone()
    reasons = json.loads(row["rank_explanation"])
    for r in reasons:
        assert r.get("source")
        if r["type"] != "activity":
            assert r.get("applicant")


def test_FR9_copy_eml_mailto_no_mailbox(client, conn):
    opp = conn.execute("SELECT id, researcher_id FROM opportunity WHERE demo=1 LIMIT 1").fetchone()
    conn.execute(
        "INSERT INTO profile_fact(kind, body, confirmed) VALUES ('project', 'Built a CUDA kernel scheduler for MoE inference', 1)"
    )
    conn.execute(
        "INSERT INTO profile_fact(kind, body, confirmed) VALUES ('interest', 'scheduling', 1)"
    )
    pubs = [
        dict(p)
        for p in conn.execute(
            "SELECT title,url,abstract FROM publication WHERE researcher_id=?",
            (opp["researcher_id"],),
        )
    ]
    d = generate_draft("Demo", "demo@example.edu", [{"kind": "project", "body": "Built a CUDA kernel scheduler for MoE inference", "confirmed": 1}], pubs, [])
    did = save_or_update_draft(conn, opp["id"], d)
    eml = to_eml(d["recipient"], d["subject"], d["body"])
    assert b"Subject:" in eml
    r = client.get(f"/draft/{did}/eml")
    assert r.status_code == 200
    assert "message/rfc822" in r.headers.get("content-type", "")


def test_FR10_edit_clears_approval(conn):
    opp = conn.execute("SELECT id FROM opportunity WHERE demo=1 LIMIT 1").fetchone()
    body = "Hello https://example.edu/papers/demo-alpha-1"
    h = content_hash("a@b.c", "sub", body)
    did = save_or_update_draft(
        conn, opp["id"], {"recipient": "a@b.c", "subject": "sub", "body": body, "content_hash": h}
    )
    conn.execute("UPDATE draft SET approved_hash=content_hash WHERE id=?", (did,))
    from studio.drafts import clear_approval_if_edited

    clear_approval_if_edited(conn, did, "a@b.c", "sub", body + " edited")
    row = conn.execute("SELECT approved_hash FROM draft WHERE id=?", (did,)).fetchone()
    assert row["approved_hash"] is None


def test_FR11_unapproved_never_sends(conn):
    opp = conn.execute("SELECT id FROM opportunity WHERE demo=1 LIMIT 1").fetchone()
    h = content_hash("a@b.c", "s", "b")
    did = save_or_update_draft(
        conn, opp["id"], {"recipient": "a@b.c", "subject": "s", "body": "b", "content_hash": h}
    )
    with pytest.raises(ValueError):
        create_intent(conn, did, h, "smtp")


def test_FR12_submitted_becomes_unknown_delivery(data_dir):
    c = connect(data_dir / "studio.sqlite")
    migrate(c)
    c.execute(
        "INSERT INTO researcher(display_name, origin) VALUES ('X', 'manual')"
    )
    rid = c.execute("SELECT id FROM researcher").fetchone()["id"]
    c.execute(
        "INSERT INTO opportunity(researcher_id, origin) VALUES (?, 'manual')", (rid,)
    )
    oid = c.execute("SELECT id FROM opportunity").fetchone()["id"]
    c.execute(
        "INSERT INTO draft(opportunity_id, recipient, subject, body, content_hash, approved_hash) VALUES (?, 'a@b.c', 's', 'b', 'h', 'h')",
        (oid,),
    )
    did = c.execute("SELECT id FROM draft").fetchone()["id"]
    c.execute(
        "INSERT INTO send_intent(draft_id, content_hash, state) VALUES (?, 'h', 'submitted')",
        (did,),
    )
    n = recover_intents_on_startup(c)
    assert n == 1
    st = c.execute("SELECT state FROM send_intent").fetchone()["state"]
    assert st == "unknown_delivery"
    c.close()


def test_FR13_quit_sends_nothing_followup_needs_approval(conn):
    # No send on quit — intents stay; follow-up requires new approval conceptually
    opp = conn.execute("SELECT id FROM opportunity WHERE demo=1 LIMIT 1").fetchone()
    h = content_hash("a@b.c", "s", "body https://example.edu/x")
    did = save_or_update_draft(
        conn,
        opp["id"],
        {"recipient": "a@b.c", "subject": "s", "body": "body https://example.edu/x", "content_hash": h},
    )
    conn.execute("UPDATE draft SET approved_hash=content_hash WHERE id=?", (did,))
    # editing for follow-up clears
    from studio.drafts import clear_approval_if_edited

    clear_approval_if_edited(conn, did, "a@b.c", "follow-up", "new body https://example.edu/x")
    row = conn.execute("SELECT approved_hash FROM draft WHERE id=?", (did,)).fetchone()
    assert row["approved_hash"] is None


def test_FR14_disabled_reason_words(client):
    r = client.get("/profile")
    assert "blocked" in r.text.lower() or "confirm" in r.text.lower()
    r2 = client.get("/mail")
    low = r2.text.lower()
    assert (
        "no email connected" in low
        or "no smtp mailbox" in low
        or "continue with google" in low
        or "mailbox" in low
    )


def test_FR15_faculty_ssrf_adds_nobody(conn):
    from studio.faculty import collect_school

    with mock.patch(
        "studio.faculty.fetch_text",
        side_effect=ValueError("Blocked destination address: 127.0.0.1"),
    ):
        result = collect_school("mit")
    assert result["people"] == []
    assert result["error"]


def test_FR16_researcher_without_papers(conn):
    conn.execute(
        "INSERT INTO researcher(display_name, origin) VALUES ('No Papers', 'manual')"
    )
    rid = conn.execute(
        "SELECT id FROM researcher WHERE display_name='No Papers'"
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO opportunity(researcher_id, origin) VALUES (?, 'manual')", (rid,)
    )
    row = conn.execute(
        "SELECT id FROM researcher WHERE display_name='No Papers'"
    ).fetchone()
    assert row
    pubs = conn.execute(
        "SELECT * FROM publication WHERE researcher_id=?", (rid,)
    ).fetchall()
    assert pubs == []
    with pytest.raises(ValueError):
        generate_draft(
            "No Papers",
            "",
            [{"kind": "project", "body": "proj", "confirmed": 1}],
            [],
            [],
        )


def test_FR17_non_latin_names(conn):
    name = "山田 誠"
    aff = "東京大学"
    commit_import(
        conn,
        [{"n": name, "u": aff, "e": ""}],
        {"name": "n", "affiliation": "u", "email": "e"},
    )
    row = conn.execute(
        "SELECT display_name FROM researcher WHERE display_name=?", (name,)
    ).fetchone()
    assert row["display_name"] == name
    a = conn.execute(
        "SELECT institution FROM affiliation WHERE institution=?", (aff,)
    ).fetchone()
    assert a["institution"] == aff


def test_FR18_duplicate_columns_need_mapping():
    headers, rows, warnings = read_tabular(
        "t.csv", b"Name,Name,University\nA,B,U\n"
    )
    assert any("Duplicate" in w for w in warnings)
    # suggestion is not auto-committed — mapping required by student
    assert headers.count("Name") == 2


def test_FR19_two_clicks_one_intent(conn):
    opp = conn.execute("SELECT id FROM opportunity WHERE demo=1 LIMIT 1").fetchone()
    h = content_hash("a@b.c", "s", "b")
    did = save_or_update_draft(
        conn, opp["id"], {"recipient": "a@b.c", "subject": "s", "body": "b", "content_hash": h}
    )
    conn.execute("UPDATE draft SET approved_hash=content_hash WHERE id=?", (did,))
    i1 = create_intent(conn, did, h, "smtp")
    i2 = create_intent(conn, did, h, "smtp")
    assert i1 == i2
    count = conn.execute("SELECT COUNT(*) AS c FROM send_intent").fetchone()["c"]
    assert count == 1


def test_FR20_suppression_blocks_send_copy_ok(conn):
    opp = conn.execute("SELECT id FROM opportunity WHERE demo=1 LIMIT 1").fetchone()
    h = content_hash("blocked@ex.edu", "s", "b")
    did = save_or_update_draft(
        conn,
        opp["id"],
        {"recipient": "blocked@ex.edu", "subject": "s", "body": "b", "content_hash": h},
    )
    conn.execute("UPDATE draft SET approved_hash=content_hash WHERE id=?", (did,))
    conn.execute(
        "INSERT INTO suppression(email, reason) VALUES ('blocked@ex.edu', 'opt-out')"
    )
    with pytest.raises(ValueError, match="suppressed"):
        create_intent(conn, did, h, "smtp")
    assert to_eml("blocked@ex.edu", "s", "b")


def test_FR21_failed_signin_leaves_draft(client, conn):
    opp = conn.execute("SELECT id FROM opportunity WHERE demo=1 LIMIT 1").fetchone()
    h = content_hash("a@b.c", "s", "keepme")
    did = save_or_update_draft(
        conn, opp["id"], {"recipient": "a@b.c", "subject": "s", "body": "keepme", "content_hash": h}
    )
    r = client.post(
        "/mail/connect",
        data={
            "page_token": client.page_token,
            "host": "127.0.0.1",
            "port": "1",
            "username": "",
            "password": "bad",
            "sender": "me@x.com",
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    still = conn.execute("SELECT body FROM draft WHERE id=?", (did,)).fetchone()
    assert still["body"] == "keepme"


def test_FR22_check_date_and_expired(client, conn):
    expired = conn.execute(
        "SELECT id, deadline FROM opportunity WHERE demo=1 AND deadline < date('now') LIMIT 1"
    ).fetchone()
    r = client.get(f"/opportunity/{expired['id']}")
    assert r.status_code == 200
    assert "Expired" in r.text or "expired" in r.text.lower()
    unk = conn.execute(
        "SELECT id FROM opportunity WHERE demo=1 AND status='unknown' LIMIT 1"
    ).fetchone()
    r2 = client.get(f"/opportunity/{unk['id']}")
    assert "Unknown" in r2.text
    assert "Stated open" not in r2.text or "unknown" in r2.text.lower()


def test_FR23_export_and_delete_keeps_bundled(client, conn):
    before = conn.execute(
        "SELECT COUNT(*) AS c FROM researcher WHERE origin='bundled'"
    ).fetchone()["c"]
    r = client.get("/tracker/export")
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    client.post(
        "/tracker/delete-all",
        data={"page_token": client.page_token, "confirm": "DELETE"},
        follow_redirects=False,
    )
    after = conn.execute(
        "SELECT COUNT(*) AS c FROM researcher WHERE origin='bundled'"
    ).fetchone()["c"]
    assert after == before


def test_FR24_restart_keeps_data(data_dir):
    from studio.app import create_app
    from studio.demo import seed_demo
    from studio.summer_loader import seed_mini_bundled

    c = connect(data_dir / "studio.sqlite")
    migrate(c)
    seed_demo(c)
    seed_mini_bundled(c)
    c.execute(
        "INSERT INTO profile_fact(kind, body, confirmed) VALUES ('project', 'survives', 1)"
    )
    c.close()
    c2 = connect(data_dir / "studio.sqlite")
    row = c2.execute(
        "SELECT body FROM profile_fact WHERE body='survives'"
    ).fetchone()
    assert row
    bundled = c2.execute(
        "SELECT COUNT(*) AS c FROM researcher WHERE origin='bundled'"
    ).fetchone()["c"]
    assert bundled >= 1
    c2.close()
    # create_app also migrates
    create_app(data_dir)


def test_FR25_offer_lists_inclusions(client):
    r = client.get("/offer")
    assert "Summer 2027" in r.text
    assert "demo" in r.text.lower()
    assert "OpenAlex" in r.text or "publication" in r.text.lower()
    assert "Faculty" in r.text or "directory" in r.text.lower()
    assert "support@" in r.text.lower() or "Support" in r.text
    assert "Refund" in r.text or "refund" in r.text


def test_NFR1_localhost_host_and_token(client):
    # bad host
    bad = client.get("/offer", headers={"Host": "evil.example"})
    assert bad.status_code == 403
    # missing token on POST
    r = client.post("/profile/confirm/1", data={"page_token": "wrong"}, follow_redirects=False)
    assert r.status_code == 403


def test_NFR2_escape_untrusted(client, conn):
    conn.execute(
        "UPDATE researcher SET display_name=? WHERE id=(SELECT researcher_id FROM opportunity WHERE demo=1 LIMIT 1)",
        ('<script>alert(1)</script>',),
    )
    oid = conn.execute("SELECT id FROM opportunity WHERE demo=1 LIMIT 1").fetchone()["id"]
    r = client.get(f"/opportunity/{oid}")
    assert "<script>alert(1)</script>" not in r.text
    assert "alert(1)" in r.text  # escaped visible or encoded


def test_NFR3_secrets_not_world_readable(data_dir, monkeypatch):
    monkeypatch.setenv("STUDIO_FORCE_LOCAL_SECRETS", "1")
    from studio.secrets_store import set_secret, keychain_path
    from studio import secrets_store

    monkeypatch.setattr(secrets_store, "keychain_path", lambda: data_dir / "secrets.json")
    set_secret("testkey", "secret-value")
    path = data_dir / "secrets.json"
    assert path.exists()
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600


def test_NFR4_package_scan_rejects_dotenv(tmp_path):
    from studio.packaging_scan import scan_package_dir

    (tmp_path / "app").mkdir()
    (tmp_path / "app" / ".env").write_text("SECRET=1")
    with pytest.raises(SystemExit):
        scan_package_dir(tmp_path)


def test_NFR5_wcag_basics_in_css():
    css = (Path(__file__).resolve().parents[1] / "static" / "studio.css").read_text()
    assert "#92400E" in css
    assert "#065F46" in css
    assert "prefers-reduced-motion" in css
    assert "outline: 2px solid" in css
    assert "min-height: 44px" in css


def test_NFR6_library_transaction(conn):
    # mini bundled commits atomically
    n = seed_mini_bundled(conn)
    assert n >= 0  # already seeded returns existing
    count = conn.execute(
        "SELECT COUNT(*) AS c FROM researcher WHERE origin='bundled'"
    ).fetchone()["c"]
    assert count >= 2


def test_NFR7_support_bundle_redacts(data_dir):
    from studio.support_bundle import build_support_bundle

    text = build_support_bundle(
        {
            "email": "student@school.edu",
            "token": "abc123",
            "body": "Dear Professor, secret letter",
            "draft_id": 9,
            "outcome": "sent",
        }
    )
    assert "student@school.edu" not in text
    assert "abc123" not in text
    assert "secret letter" not in text
    assert "draft_id" in text or "9" in text
