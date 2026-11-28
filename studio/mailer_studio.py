"""Send intents — never auto-retry; crash mid-send becomes unknown_delivery."""

from __future__ import annotations

import smtplib
import time
from email.message import EmailMessage
from typing import Any


def create_intent(conn, draft_id: int, content_hash: str, provider: str = "smtp") -> int:
    # Lock by unique content_hash — second click returns existing
    existing = conn.execute(
        "SELECT id, state FROM send_intent WHERE content_hash = ?",
        (content_hash,),
    ).fetchone()
    if existing:
        return int(existing["id"])
    # Only if approved
    draft = conn.execute("SELECT * FROM draft WHERE id = ?", (draft_id,)).fetchone()
    if not draft or draft["approved_hash"] != draft["content_hash"]:
        raise ValueError("Draft is not approved")
    # suppression check
    suppressed = conn.execute(
        "SELECT id FROM suppression WHERE email = ?",
        (draft["recipient"],),
    ).fetchone()
    if suppressed:
        raise ValueError("Recipient is suppressed")
    cur = conn.execute(
        """
        INSERT INTO send_intent(draft_id, content_hash, state, provider)
        VALUES (?, ?, 'pending', ?)
        """,
        (draft_id, content_hash, provider),
    )
    return int(cur.lastrowid)


def mark_submitted(conn, intent_id: int) -> None:
    conn.execute(
        """
        UPDATE send_intent SET state = 'submitted', updated_at = datetime('now')
        WHERE id = ? AND state = 'pending'
        """,
        (intent_id,),
    )


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
) -> str:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)
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
    mark_submitted(conn, intent_id)
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
