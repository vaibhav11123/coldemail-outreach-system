"""Deadline → reminder writers for the application tracker."""

from __future__ import annotations

from datetime import date, timedelta


def sync_deadline_reminders(conn) -> int:
    """Ensure each application with a near-term deadline has a reminder row.

    Returns number of reminders inserted.
    """
    today = date.today()
    horizon = today + timedelta(days=21)
    apps = conn.execute(
        """
        SELECT id, deadline, state FROM application
        WHERE deadline IS NOT NULL AND deadline != ''
          AND state NOT IN ('rejected', 'stopped')
        """
    ).fetchall()
    inserted = 0
    for a in apps:
        try:
            due = date.fromisoformat(str(a["deadline"])[:10])
        except ValueError:
            continue
        if due < today or due > horizon:
            continue
        existing = conn.execute(
            """
            SELECT id FROM reminder
            WHERE application_id=? AND kind='deadline' AND dismissed=0
            """,
            (a["id"],),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE reminder SET due_on=? WHERE id=?",
                (due.isoformat(), existing["id"]),
            )
            continue
        conn.execute(
            """
            INSERT INTO reminder(application_id, due_on, kind, dismissed)
            VALUES (?, ?, 'deadline', 0)
            """,
            (a["id"], due.isoformat()),
        )
        inserted += 1

    # Follow-up: submitted_by_me older than 10 days without a followup reminder
    follow = conn.execute(
        """
        SELECT id, updated_at FROM application
        WHERE state='submitted_by_me'
        """
    ).fetchall()
    for a in follow:
        try:
            updated = date.fromisoformat(str(a["updated_at"])[:10])
        except ValueError:
            continue
        if (today - updated).days < 10:
            continue
        existing = conn.execute(
            """
            SELECT id FROM reminder
            WHERE application_id=? AND kind='followup' AND dismissed=0
            """,
            (a["id"],),
        ).fetchone()
        if existing:
            continue
        due_on = (updated + timedelta(days=10)).isoformat()
        conn.execute(
            """
            INSERT INTO reminder(application_id, due_on, kind, dismissed)
            VALUES (?, ?, 'followup', 0)
            """,
            (a["id"], due_on),
        )
        inserted += 1
    return inserted


def open_reminders(conn) -> list[dict]:
    rows = conn.execute(
        """
        SELECT rem.id, rem.due_on, rem.kind, rem.application_id,
               r.display_name AS name
        FROM reminder rem
        JOIN application a ON a.id = rem.application_id
        JOIN opportunity o ON o.id = a.opportunity_id
        JOIN researcher r ON r.id = o.researcher_id
        WHERE rem.dismissed=0
        ORDER BY rem.due_on ASC
        """
    ).fetchall()
    return [dict(r) for r in rows]


KANBAN_COLUMNS = [
    ("Preparing", {"drafted", "ready"}),
    ("Applied", {"submitted_by_me"}),
    ("In conversation", {"replied", "interview"}),
    ("Closed", {"rejected", "stopped"}),
]


def group_kanban(items: list) -> list[dict]:
    buckets = {label: [] for label, _ in KANBAN_COLUMNS}
    for item in items:
        state = item["state"] if isinstance(item, dict) else item["state"]
        placed = False
        for label, states in KANBAN_COLUMNS:
            if state in states:
                buckets[label].append(item)
                placed = True
                break
        if not placed:
            buckets["Preparing"].append(item)
    # Use "cards" not "items" — Jinja treats .items as dict.items()
    return [{"label": label, "cards": buckets[label]} for label, _ in KANBAN_COLUMNS]
