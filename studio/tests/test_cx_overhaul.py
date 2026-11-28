"""Customer-experience overhaul: nav, layouts and key page presentation."""

from __future__ import annotations

import pytest


def _seed_profile(client):
    for kind, body in (
        ("interest", "GPU kernel optimization"),
        ("project", "Built a CUDA matmul"),
    ):
        client.post(
            "/profile",
            data={"page_token": client.page_token, kind: body, "mode": "internship"},
            follow_redirects=False,
        )


def _confirm_all(client, conn):
    conn.execute("UPDATE profile_fact SET confirmed=1")


def test_nav_brand_and_workspace_links(client):
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "Academic <span>Studio</span>" in r.text
    for label in ("Overview", "Faculty library", "Research matches", "My shortlist", "Compare", "Applications"):
        assert label in r.text
    for label in ("My profile", "Settings", "Help", "Licence", "Purchased catalog"):
        assert label in r.text
    assert 'class="layout-workspace"' in r.text


def test_planner_and_hosted_hidden_by_default(client, monkeypatch):
    monkeypatch.delenv("STUDIO_ENABLE_HR_PLANNER", raising=False)
    monkeypatch.delenv("STUDIO_SHOW_HOSTED", raising=False)
    r = client.get("/dashboard")
    assert 'href="/planner"' not in r.text
    assert 'href="/hosted"' not in r.text


def test_planner_and_hosted_shown_when_enabled(client, monkeypatch):
    monkeypatch.setenv("STUDIO_ENABLE_HR_PLANNER", "1")
    monkeypatch.setenv("STUDIO_SHOW_HOSTED", "1")
    r = client.get("/dashboard")
    assert 'href="/planner"' in r.text
    assert 'href="/hosted"' in r.text


def test_planner_copy_never_claims_test_mode_sends(client):
    r = client.get("/planner")
    assert r.status_code == 200
    assert "Test mode still sends" not in r.text
    assert "never send email" in r.text


def test_layout_classes_per_page(client, conn):
    assert 'class="layout-workspace"' in client.get("/directory").text
    assert 'class="layout-workspace"' in client.get("/tracker").text
    assert 'class="layout-workspace"' in client.get("/compare").text
    assert 'class="layout-focus"' in client.get("/activate").text
    oid = conn.execute("SELECT id FROM opportunity LIMIT 1").fetchone()["id"]
    assert 'class="layout-split"' in client.get(f"/draft/{oid}").text


def test_directory_has_compare_checkboxes_and_tri_state(client):
    r = client.get("/directory")
    assert 'name="compare_ids"' in r.text
    assert 'action="/compare"' in r.text
    assert "stated-yes" not in r.text.split("<tbody>", 1)[-1].split("</tbody>", 1)[0]


def test_compare_accepts_compare_ids(client, conn):
    rid = conn.execute("SELECT id FROM researcher LIMIT 1").fetchone()["id"]
    r = client.get(f"/compare?compare_ids={rid}")
    assert r.status_code == 200
    assert "Institution" in r.text
    assert "comma-separated" not in r.text


def test_tracker_has_no_inline_delete(client):
    r = client.get("/tracker")
    assert "Delete all my data" not in r.text
    assert 'action="/tracker/delete-all"' not in r.text
    settings = client.get("/connections")
    assert 'action="/tracker/delete-all"' in settings.text
    assert 'id="privacy"' in settings.text


def test_tracker_uses_human_states(client, conn):
    oid = conn.execute("SELECT id FROM opportunity LIMIT 1").fetchone()["id"]
    conn.execute("INSERT INTO application(opportunity_id, state) VALUES (?, 'submitted_by_me')", (oid,))
    r = client.get("/tracker")
    assert "Submitted manually" in r.text
    t = client.get("/tracker/timeline")
    assert t.status_code == 200
    assert "Submitted manually" in t.text


def test_opportunity_expired_demotes_prepare(client, conn):
    expired = conn.execute(
        "SELECT id FROM opportunity WHERE demo=1 AND deadline < date('now') LIMIT 1"
    ).fetchone()
    r = client.get(f"/opportunity/{expired['id']}")
    assert "Expired" in r.text
    assert "Prepare application anyway" in r.text
    assert r.text.count("Prepare application") == 1
    assert "Demo opening" in r.text
    assert "Last verified" in r.text


def test_opportunity_open_has_single_primary_prepare(client, conn):
    row = conn.execute(
        "SELECT id FROM opportunity WHERE demo=1 AND (deadline IS NULL OR deadline >= date('now')) LIMIT 1"
    ).fetchone()
    r = client.get(f"/opportunity/{row['id']}")
    assert r.status_code == 200
    assert r.text.count(">Prepare application<") == 1


def test_draft_blocks_approve_on_hard_fail(client, conn):
    opp = conn.execute("SELECT id FROM opportunity WHERE demo=1 LIMIT 1").fetchone()
    from studio.drafts import content_hash, save_or_update_draft

    body = 'I cite "Totally fake paper title xyzzy" (https://evil.example/nope).'
    h = content_hash("a@b.c", "s", body)
    save_or_update_draft(
        conn, opp["id"], {"recipient": "a@b.c", "subject": "s", "body": body, "content_hash": h}
    )
    r = client.get(f"/draft/{opp['id']}")
    assert r.status_code == 200
    assert "Must fix" in r.text
    approve = r.text.split('value="approve"', 1)[1].split(">", 1)[0]
    assert "disabled" in approve


def test_drafts_empty_state_links(client):
    r = client.get("/drafts")
    assert "Choose researcher" in r.text
    assert "Browse directory" in r.text


def test_shortlist_views_and_filters(client, conn):
    _seed_profile(client)
    _confirm_all(client, conn)
    client.post("/shortlist/rebuild", data={"page_token": client.page_token}, follow_redirects=False)
    rec = client.get("/shortlist?view=recommended")
    assert rec.status_code == 200
    assert "Recommended for you" in rec.text
    assert "Hide unknowns" not in rec.text
    assert "Funding mentioned only" in rec.text
    allv = client.get("/shortlist")
    assert "My shortlist" in allv.text


def test_profile_single_progress(client):
    r = client.get("/profile")
    assert "1 of 3" in r.text
    assert "Skip for now" in r.text
    assert 'href="/directory"' in r.text
    assert "Step 1 of 3" not in r.text
    assert "5 · Track" not in r.text


def test_offer_dataset_first(client):
    r = client.get("/offer")
    assert "Get the dataset" in r.text
    assert "1,021" in r.text
    assert "2,982" in r.text


def test_reader_hides_licence_details_from_hero(client):
    r = client.get("/reader")
    assert "Faculty Library" in r.text
    assert "SQLCipher" not in r.text.split("</section>", 1)[0]


def test_return_has_no_retention_language(client):
    r = client.get("/return")
    assert "retention" not in r.text.lower()


def test_backup_summary_and_restore_confirmation(client):
    r = client.get("/backup")
    assert "What a backup contains" in r.text
    assert "replaces my current workspace" in r.text


def test_activate_install_error_renders_page(client):
    r = client.post(
        "/activate",
        data={
            "page_token": client.page_token,
            "action": "install_aslic",
            "package_dir": "/nonexistent-folder-xyz",
        },
        files={"aslic_file": ("CustomerLicense.aslic", b"{}", "application/json")},
    )
    assert r.status_code == 200
    assert "Delivery folder" in r.text


@pytest.mark.parametrize(
    "path",
    ["/dashboard", "/offer", "/profile", "/start", "/demo", "/directory", "/compare",
     "/shortlist", "/drafts", "/tracker", "/tracker/timeline", "/connections", "/ai",
     "/mail", "/backup", "/return", "/activate", "/activate/help", "/reader"],
)
def test_pages_render(client, path):
    assert client.get(path).status_code == 200
