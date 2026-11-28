"""INV-01/02/03/13/14/15 — email approval, duplicates, crash, suppression."""

from __future__ import annotations

import threading
from unittest import mock

import pytest

from studio.db import recover_intents_on_startup
from studio.drafts import clear_approval_if_edited, content_hash
from studio.mailer_studio import create_intent, mark_submitted, perform_send, reconcile_unknown


def test_INV01_unapproved_cannot_create_intent(conn, approved_draft):
    conn.execute(
        "UPDATE draft SET approved_hash = NULL WHERE id = ?", (approved_draft["id"],)
    )
    with pytest.raises(ValueError, match="not approved"):
        create_intent(conn, approved_draft["id"], approved_draft["content_hash"])


def test_INV13_edit_clears_approval_blocks_send(conn, approved_draft):
    clear_approval_if_edited(
        conn,
        approved_draft["id"],
        approved_draft["recipient"],
        "changed subject",
        approved_draft["body"],
    )
    row = conn.execute(
        "SELECT approved_hash, content_hash FROM draft WHERE id = ?",
        (approved_draft["id"],),
    ).fetchone()
    assert row["approved_hash"] is None
    with pytest.raises(ValueError, match="not approved"):
        create_intent(conn, approved_draft["id"], row["content_hash"])


def test_INV03_double_create_intent_same_hash(conn, approved_draft):
    a = create_intent(conn, approved_draft["id"], approved_draft["content_hash"])
    b = create_intent(conn, approved_draft["id"], approved_draft["content_hash"])
    assert a == b
    n = conn.execute("SELECT COUNT(*) AS c FROM send_intent").fetchone()["c"]
    assert n == 1


def test_INV03_concurrent_claim_single_provider_call(conn, approved_draft, data_dir):
    """Two connections racing mark_submitted — only one may claim pending→submitted."""
    intent = create_intent(conn, approved_draft["id"], approved_draft["content_hash"])
    from studio.db import connect

    db = data_dir / "studio.sqlite"
    hits: list[bool] = []
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def worker():
        c = connect(db)
        try:
            barrier.wait(timeout=5)
            hits.append(mark_submitted(c, intent))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            c.close()

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert not errors
    assert hits.count(True) == 1
    assert hits.count(False) == 1
    state = conn.execute(
        "SELECT state FROM send_intent WHERE id = ?", (intent,)
    ).fetchone()["state"]
    assert state == "submitted"


def test_INV02_unknown_delivery_blocks_auto_resend(conn, approved_draft):
    intent = create_intent(conn, approved_draft["id"], approved_draft["content_hash"])
    mark_submitted(conn, intent)
    n = recover_intents_on_startup(conn)
    assert n >= 1
    state = conn.execute(
        "SELECT state FROM send_intent WHERE id = ?", (intent,)
    ).fetchone()["state"]
    assert state == "unknown_delivery"
    with pytest.raises(ValueError, match="unknown"):
        create_intent(conn, approved_draft["id"], approved_draft["content_hash"])
    with pytest.raises(ValueError, match="[Uu]nknown"):
        perform_send(conn, intent, smtp_config={"host": "x", "port": 25})


def test_INV02_reconcile_then_no_automatic_second_send(conn, approved_draft):
    intent = create_intent(conn, approved_draft["id"], approved_draft["content_hash"])
    mark_submitted(conn, intent)
    recover_intents_on_startup(conn)
    reconcile_unknown(conn, intent, "sent")
    # Sent content must not spawn a new provider submission via create_intent+perform
    reused = create_intent(conn, approved_draft["id"], approved_draft["content_hash"])
    assert reused == intent
    assert perform_send(conn, reused, smtp_config={"host": "x", "port": 25}) == "already_sent"


def test_INV14_suppressed_recipient_blocked(conn, approved_draft):
    conn.execute(
        "INSERT INTO suppression(email, reason) VALUES (?, ?)",
        (approved_draft["recipient"], "student request"),
    )
    with pytest.raises(ValueError, match="suppressed"):
        create_intent(conn, approved_draft["id"], approved_draft["content_hash"])


def test_INV15_failed_send_allows_explicit_retry(conn, approved_draft):
    intent = create_intent(conn, approved_draft["id"], approved_draft["content_hash"])
    with mock.patch(
        "studio.mailer_studio.send_via_smtp",
        side_effect=RuntimeError("smtp down"),
    ):
        with pytest.raises(RuntimeError, match="smtp down"):
            perform_send(
                conn,
                intent,
                smtp_config={
                    "host": "localhost",
                    "port": 1025,
                    "username": "",
                    "password": "",
                    "sender": "me@example.com",
                    "use_tls": False,
                },
            )
    state = conn.execute(
        "SELECT state FROM send_intent WHERE id = ?", (intent,)
    ).fetchone()["state"]
    assert state == "failed"
    # Explicit second click may retry
    again = create_intent(conn, approved_draft["id"], approved_draft["content_hash"])
    assert again == intent
    pending = conn.execute(
        "SELECT state FROM send_intent WHERE id = ?", (intent,)
    ).fetchone()["state"]
    assert pending == "pending"
    with mock.patch(
        "studio.mailer_studio.send_via_smtp",
        return_value="smtp:1",
    ):
        assert (
            perform_send(
                conn,
                again,
                smtp_config={
                    "host": "localhost",
                    "port": 1025,
                    "username": "",
                    "password": "",
                    "sender": "me@example.com",
                    "use_tls": False,
                },
            )
            == "sent"
        )


def test_INV03_hundred_rapid_create_intents(conn, approved_draft):
    ids = [
        create_intent(conn, approved_draft["id"], approved_draft["content_hash"])
        for _ in range(100)
    ]
    assert len(set(ids)) == 1
    assert conn.execute("SELECT COUNT(*) AS c FROM send_intent").fetchone()["c"] == 1


def test_INV01_stale_hash_rejected(conn, approved_draft):
    with pytest.raises(ValueError, match="changed|not approved"):
        create_intent(conn, approved_draft["id"], "not-the-real-hash")
