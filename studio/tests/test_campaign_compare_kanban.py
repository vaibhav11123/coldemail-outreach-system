"""Campaign dashboard, compare matrix, Kanban reminders, backup, saved search."""

from __future__ import annotations

from pathlib import Path

from studio.backup import create_backup, restore_backup
from studio.campaign import build_campaign_snapshot
from studio.compare import comparison_rows
from studio.reminders import group_kanban, sync_deadline_reminders


def test_home_redirects_to_dashboard(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert "/dashboard" in r.headers["location"]


def test_dashboard_renders(client):
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "What to do next" in r.text


def test_campaign_snapshot_actions(conn):
    snap = build_campaign_snapshot(conn, profile_ready=False)
    assert snap.actions
    assert any("CV" in a.title or "profile" in a.title.lower() for a in snap.actions)


def test_compare_page_and_rows(client, conn):
    rid = conn.execute("SELECT id FROM researcher LIMIT 1").fetchone()["id"]
    facts = [dict(f) for f in conn.execute("SELECT * FROM profile_fact").fetchall()]
    rows = comparison_rows(conn, [rid], facts)
    assert rows
    assert rows[0]["name"]
    r = client.get(f"/compare?ids={rid}")
    assert r.status_code == 200
    assert "Professor comparison" in r.text


def test_kanban_groups_and_reminders(conn):
    oid = conn.execute("SELECT id FROM opportunity LIMIT 1").fetchone()["id"]
    conn.execute(
        """
        INSERT INTO application(opportunity_id, channel, state, deadline)
        VALUES (?, 'email', 'drafted', date('now', '+5 days'))
        """,
        (oid,),
    )
    n = sync_deadline_reminders(conn)
    assert n >= 1
    items = [
        {"state": "drafted", "name": "A"},
        {"state": "submitted_by_me", "name": "B"},
        {"state": "replied", "name": "C"},
        {"state": "rejected", "name": "D"},
    ]
    cols = group_kanban(items)
    assert [c["label"] for c in cols] == [
        "Preparing",
        "Applied",
        "In conversation",
        "Closed",
    ]
    assert len(cols[0]["cards"]) == 1


def test_tracker_kanban_ui(client, conn):
    oid = conn.execute("SELECT id FROM opportunity LIMIT 1").fetchone()["id"]
    conn.execute(
        "INSERT INTO application(opportunity_id, state) VALUES (?, 'ready')",
        (oid,),
    )
    r = client.get("/tracker")
    assert r.status_code == 200
    assert "Application Kanban" in r.text
    assert "Preparing" in r.text


def test_saved_search_roundtrip(client):
    r = client.post(
        "/directory/save-search",
        data={
            "page_token": client.page_token,
            "name": "GPU labs",
            "q": "GPU",
            "funding": "",
            "status": "",
            "university": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    again = client.get("/directory")
    assert "GPU labs" in again.text


def test_backup_create_restore(tmp_path, monkeypatch):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    db = workspace / "studio.sqlite"
    import sqlite3

    c = sqlite3.connect(db)
    c.execute("CREATE TABLE t(x)")
    c.execute("INSERT INTO t VALUES (1)")
    c.commit()
    c.close()
    (workspace / "attachments").mkdir()
    (workspace / "attachments" / "note.txt").write_text("hello", encoding="utf-8")
    z = create_backup(workspace)
    assert z.is_file()
    # wipe and restore
    db.unlink()
    restore_backup(z, workspace)
    c = sqlite3.connect(workspace / "studio.sqlite")
    assert c.execute("SELECT x FROM t").fetchone()[0] == 1
    c.close()
    assert (workspace / "attachments" / "note.txt").read_text(encoding="utf-8") == "hello"


def test_editions_two_sold_skus():
    from studio.licensing.products import SKU, editions, get_edition

    sold = editions()
    assert set(sold) == {SKU.STANDARD_DATASET, SKU.ACADEMIC_STUDIO}
    assert get_edition(SKU.PROTECTED_DATASET).sold_separately is False
    assert get_edition(SKU.ACADEMIC_STUDIO).licence_included is True
