"""Campaign dashboard — what the student should do next."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Any


@dataclass
class NextAction:
    title: str
    href: str
    detail: str = ""
    priority: int = 50


@dataclass
class CampaignSnapshot:
    shortlisted: int = 0
    preparing: int = 0
    applied: int = 0
    responses: int = 0
    profile_ready: bool = False
    actions: list[NextAction] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            **{k: v for k, v in asdict(self).items() if k != "actions"},
            "actions": [asdict(a) for a in self.actions],
        }


def build_campaign_snapshot(conn, *, profile_ready: bool) -> CampaignSnapshot:
    shortlisted = conn.execute("SELECT COUNT(*) AS c FROM shortlist_item").fetchone()["c"]
    apps = [
        dict(r)
        for r in conn.execute(
            """
            SELECT a.id, a.state, a.deadline, a.opportunity_id, r.display_name AS name
            FROM application a
            JOIN opportunity o ON o.id = a.opportunity_id
            JOIN researcher r ON r.id = o.researcher_id
            """
        )
    ]
    preparing = sum(1 for a in apps if a["state"] in {"drafted", "ready"})
    applied = sum(1 for a in apps if a["state"] == "submitted_by_me")
    responses = sum(1 for a in apps if a["state"] in {"replied", "interview"})

    snap = CampaignSnapshot(
        shortlisted=int(shortlisted),
        preparing=preparing,
        applied=applied,
        responses=responses,
        profile_ready=profile_ready,
    )
    actions: list[NextAction] = []
    if not profile_ready:
        actions.append(
            NextAction(
                "Import or confirm your CV profile",
                "/profile",
                "Confirm at least one interest plus a project, skill, or coursework line.",
                priority=10,
            )
        )
    if profile_ready and shortlisted == 0:
        actions.append(
            NextAction(
                "Discover matching professors",
                "/directory",
                "Search the catalog, then rebuild your shortlist.",
                priority=20,
            )
        )
        actions.append(
            NextAction(
                "Rebuild research shortlist",
                "/shortlist",
                "Rank openings from your confirmed profile.",
                priority=25,
            )
        )
    if shortlisted and preparing < min(5, shortlisted):
        actions.append(
            NextAction(
                f"Prepare applications from your shortlist ({shortlisted} ranked)",
                "/shortlist",
                "Open a faculty page and write an evidence-grounded letter.",
                priority=30,
            )
        )
    unfinished = [a for a in apps if a["state"] in {"drafted", "ready"}]
    if unfinished:
        actions.append(
            NextAction(
                f"Finish {len(unfinished)} unfinished application(s)",
                "/tracker",
                "Move drafts to ready, approve, and send or export .eml.",
                priority=35,
            )
        )
    today = date.today()
    soon = today + timedelta(days=14)
    due = []
    for a in apps:
        if not a.get("deadline"):
            continue
        try:
            d = date.fromisoformat(str(a["deadline"])[:10])
        except ValueError:
            continue
        if today <= d <= soon and a["state"] not in {"rejected", "stopped"}:
            due.append(a)
    if due:
        actions.append(
            NextAction(
                f"Review {len(due)} deadline(s) in the next 14 days",
                "/tracker",
                ", ".join(f"{a['name']} ({a['deadline']})" for a in due[:3]),
                priority=15,
            )
        )
    # Follow-ups: submitted with no reply yet and older than reminder
    follow = [
        a
        for a in apps
        if a["state"] == "submitted_by_me"
    ]
    if follow:
        actions.append(
            NextAction(
                f"Review {len(follow)} sent application(s) for follow-up",
                "/tracker",
                "Check whether a polite follow-up is appropriate.",
                priority=40,
            )
        )
    if not actions:
        actions.append(
            NextAction(
                "Explore the faculty directory",
                "/directory",
                "Your workspace is ready — keep discovering researchers.",
                priority=90,
            )
        )
    actions.sort(key=lambda a: a.priority)
    snap.actions = actions[:6]
    return snap
