"""Prod-qual fixtures (parent studio/tests/conftest.py is already loaded)."""

from __future__ import annotations

import pytest


@pytest.fixture()
def approved_draft(conn):
    """Minimal approved draft grounded in demo evidence."""
    from studio.drafts import content_hash, save_or_update_draft

    opp = conn.execute(
        "SELECT o.id, r.email FROM opportunity o "
        "JOIN researcher r ON r.id = o.researcher_id "
        "WHERE o.demo = 1 LIMIT 1"
    ).fetchone()
    assert opp is not None
    body = (
        "Dear Demo,\n\n"
        "I am writing about your paper \"Demo paper on transformers\" "
        "(https://example.edu/papers/demo-1). "
        "My recent project: Built a small transformer demo. "
        "I would like to explore whether this connects with openings in your group.\n\n"
        "Thank you for your time,\n"
    )
    recipient = opp["email"] or "demo@example.edu"
    subject = "Interest in your work"
    h = content_hash(recipient, subject, body)
    did = save_or_update_draft(
        conn,
        opp["id"],
        {
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "content_hash": h,
        },
    )
    conn.execute(
        "UPDATE draft SET approved_hash = content_hash WHERE id = ?", (did,)
    )
    row = conn.execute("SELECT * FROM draft WHERE id = ?", (did,)).fetchone()
    return row
