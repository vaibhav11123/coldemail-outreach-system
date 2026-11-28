"""Send intents — never auto-retry; crash mid-send becomes unknown_delivery."""

from __future__ import annotations

import os
import smtplib
import time
from email.message import EmailMessage
from typing import Any


def mail_transport_mode() -> str:
    """Customer-safe transport modes.

    - ``preview`` / ``simulation``: never contact a real SMTP/Gmail provider
    - ``send_test``: only allowed when recipient matches STUDIO_MAIL_TEST_RECIPIENT
    - ``production``: real send (default when credentials exist)
    """
    raw = (os.environ.get("STUDIO_MAIL_MODE") or "").strip().lower()
    if raw in {"preview", "simulation", "send_test", "production"}:
        return raw
    if (os.environ.get("STUDIO_MAIL_DRY_RUN") or "").strip().lower() in {"1", "true", "yes"}:
        return "simulation"
    return "production"


def create_intent(conn, draft_id: int, content_hash: str, provider: str = "smtp") -> int:
    """Create or reuse a send intent. Never invent a second intent for the same hash.

    - ``sent`` / ``pending`` / ``submitted`` → return existing id (caller must not double-send).
    - ``unknown_delivery`` → refuse automatic retry (manual reconcile only).
    - ``failed`` → reset to ``pending`` so the student can explicitly retry once.
    """
    draft = conn.execute("SELECT * FROM draft WHERE id = ?", (draft_id,)).fetchone()
    if not draft or draft["approved_hash"] != draft["content_hash"]:
        raise ValueError("Draft is not approved")
    if draft["content_hash"] != content_hash:
        raise ValueError("Draft content changed; re-approve before sending")
    suppressed = conn.execute(
        "SELECT id FROM suppression WHERE email = ?",
        (draft["recipient"],),
    ).fetchone()
    if suppressed:
        raise ValueError("Recipient is suppressed")

    existing = conn.execute(
        "SELECT id, state FROM send_intent WHERE content_hash = ?",
        (content_hash,),
    ).fetchone()
    if existing:
        state = existing["state"]
        if state == "unknown_delivery":
            raise ValueError(
                "Delivery status is unknown. Reconcile this send before trying again."
            )
        if state == "failed":
            conn.execute(
                """
                UPDATE send_intent
                SET state = 'pending', error = NULL, provider = ?,
                    provider_message_id = NULL, updated_at = datetime('now')
                WHERE id = ? AND state = 'failed'
                """,
                (provider, existing["id"]),
            )
        return int(existing["id"])

    cur = conn.execute(
        """
        INSERT INTO send_intent(draft_id, content_hash, state, provider)
        VALUES (?, ?, 'pending', ?)
        """,
        (draft_id, content_hash, provider),
    )
    return int(cur.lastrowid)


def mark_submitted(conn, intent_id: int) -> bool:
    """Atomically claim a pending intent. Returns False if another worker already claimed it."""
    cur = conn.execute(
        """
        UPDATE send_intent SET state = 'submitted', updated_at = datetime('now')
        WHERE id = ? AND state = 'pending'
        """,
        (intent_id,),
    )
    return cur.rowcount == 1


def mark_sent(conn, intent_id: int, provider_message_id: str | None = None) -> None:
    conn.execute(
        """
        UPDATE send_intent
        SET state = 'sent', provider_message_id = ?, updated_at = datetime('now')
        WHERE id = ? AND state = 'submitted'
        """,
        (provider_message_id, intent_id),
    )


def mark_failed(conn, intent_id: int, error: str) -> None:
    conn.execute(
        """
        UPDATE send_intent
        SET state = 'failed', error = ?, updated_at = datetime('now')
        WHERE id = ? AND state IN ('pending', 'submitted')
        """,
        (error, intent_id),
    )


def send_via_smtp(
    host: str,
    port: int,
    username: str,
    password: str,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    use_tls: bool = True,
    use_ssl: bool = False,
) -> str:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)
    # Port 465 → implicit TLS (common for IIT / institutional SMTPS)
    if use_ssl or int(port) == 465:
        with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
            if username:
                smtp.login(username, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            if use_tls:
                smtp.starttls()
            if username:
                smtp.login(username, password)
            smtp.send_message(msg)
    return f"smtp:{int(time.time())}"


def perform_send(
    conn,
    intent_id: int,
    smtp_config: dict[str, Any] | None = None,
) -> str:
    """
    Transition pending -> submitted -> sent/failed.
    Caller must not auto-retry unknown_delivery.
    Provider is taken from the send_intent row (gmail | smtp).
    """
    intent = conn.execute("SELECT * FROM send_intent WHERE id = ?", (intent_id,)).fetchone()
    if not intent:
        raise ValueError("Intent not found")
    if intent["state"] == "sent":
        return "already_sent"
    if intent["state"] == "unknown_delivery":
        raise ValueError("Unknown delivery requires manual reconciliation")
    if intent["state"] != "pending":
        raise ValueError(f"Cannot send from state {intent['state']}")

    draft = conn.execute("SELECT * FROM draft WHERE id = ?", (intent["draft_id"],)).fetchone()
    if not draft:
        raise ValueError("Draft missing")
    if draft["approved_hash"] != draft["content_hash"]:
        raise ValueError("Approval cleared")

    provider = (intent["provider"] or "smtp").lower()
    mode = mail_transport_mode()
    if mode in {"preview", "simulation"}:
        if not mark_submitted(conn, intent_id):
            raise ValueError("Send already in progress or completed")
        mid = f"sim:{mode}:{int(time.time())}"
        mark_sent(conn, intent_id, mid)
        return "simulated"
    if mode == "send_test":
        allowed = (os.environ.get("STUDIO_MAIL_TEST_RECIPIENT") or "").strip().lower()
        if not allowed or (draft["recipient"] or "").strip().lower() != allowed:
            raise ValueError(
                "Send-test mode only delivers to STUDIO_MAIL_TEST_RECIPIENT. "
                "Confirm the test recipient before sending."
            )
    # Atomic claim — concurrent double-submit must not both hit the provider.
    if not mark_submitted(conn, intent_id):
        refreshed = conn.execute(
            "SELECT state FROM send_intent WHERE id = ?", (intent_id,)
        ).fetchone()
        if refreshed and refreshed["state"] == "sent":
            return "already_sent"
        raise ValueError("Send already in progress or completed")
    try:
        if provider == "gmail":
            from studio.mail.gmail import send_via_gmail

            result = send_via_gmail(
                recipient=draft["recipient"],
                subject=draft["subject"],
                body=draft["body"],
            )
            mid = result.get("provider_message_id") or ""
            thread = result.get("thread_id") or ""
            if thread:
                mid = f"{mid}|thread:{thread}" if mid else f"thread:{thread}"
        else:
            if not smtp_config:
                raise ValueError("SMTP settings missing")
            mid = send_via_smtp(
                host=smtp_config["host"],
                port=int(smtp_config.get("port", 587)),
                username=smtp_config.get("username", ""),
                password=smtp_config.get("password", ""),
                sender=smtp_config.get(
                    "sender", smtp_config.get("username", "studio@localhost")
                ),
                recipient=draft["recipient"],
                subject=draft["subject"],
                body=draft["body"],
                use_tls=bool(smtp_config.get("use_tls", True)),
                use_ssl=bool(smtp_config.get("use_ssl", False)),
            )
        mark_sent(conn, intent_id, mid)
        app = conn.execute(
            "SELECT id FROM application WHERE opportunity_id = ?",
            (draft["opportunity_id"],),
        ).fetchone()
        if app:
            conn.execute(
                "UPDATE application SET state = 'submitted_by_me', updated_at=datetime('now') WHERE id = ?",
                (app["id"],),
            )
        return "sent"
    except Exception as exc:  # noqa: BLE001
        mark_failed(conn, intent_id, str(exc))
        raise


def reconcile_unknown(conn, intent_id: int, outcome: str) -> None:
    if outcome not in {"sent", "failed"}:
        raise ValueError("outcome must be sent or failed")
    conn.execute(
        """
        UPDATE send_intent SET state = ?, updated_at = datetime('now')
        WHERE id = ? AND state = 'unknown_delivery'
        """,
        (outcome, intent_id),
    )
