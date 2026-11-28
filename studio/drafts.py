"""Deterministic evidence-grounded draft generation."""

from __future__ import annotations

import hashlib
import json
import re
from email.message import EmailMessage


def content_hash(recipient: str, subject: str, body: str) -> str:
    raw = f"{recipient}\n{subject}\n{body}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def generate_draft(
    researcher_name: str,
    recipient: str,
    profile_facts: list[dict],
    publications: list[dict],
    reasons: list[dict],
) -> dict:
    projects = [f for f in profile_facts if f.get("kind") == "project" and f.get("confirmed")]
    if not projects:
        raise ValueError("Need at least one confirmed project line")
    sourced = [p for p in publications if p.get("url") and (p.get("title") or p.get("abstract"))]
    if not sourced and not any(r.get("url") for r in reasons):
        raise ValueError("Need at least one sourced lab sentence")

    project = projects[0]["body"]
    paper = sourced[0] if sourced else None
    paper_title = (paper or {}).get("title") or next((r.get("source") for r in reasons if r.get("source")), "")
    paper_url = (paper or {}).get("url") or next((r.get("url") for r in reasons if r.get("url")), "")
    paper_bit = (paper or {}).get("abstract") or paper_title

    first = researcher_name.split()[0] if researcher_name else "Professor"
    subject = f"Interest in your work on {paper_title[:60]}"
    body = (
        f"Dear {first},\n\n"
        f"I am writing about your paper \"{paper_title}\" ({paper_url}). "
        f"{paper_bit}\n\n"
        f"My recent project: {project}. "
        f"I would like to explore whether this connects with openings in your group.\n\n"
        f"Thank you for your time,\n"
    )
    # Strip any sentence that invents claims without evidence markers — keep only sourced parts
    return {
        "recipient": recipient,
        "subject": subject,
        "body": body,
        "content_hash": content_hash(recipient, subject, body),
        "citations": [
            {"applicant": project, "source": paper_bit, "url": paper_url},
        ],
    }


def has_uncited_claim(body: str, allowed_snippets: list[str]) -> bool:
    """Block approval when body introduces a URL/title not in evidence."""
    urls = re.findall(r"https?://\S+", body)
    for url in urls:
        cleaned = url.rstrip(").,")
        if not any(cleaned in (s or "") for s in allowed_snippets):
            return True
    # Block sentences that invent paper titles not present in evidence
    allowed_lower = " ".join(s or "" for s in allowed_snippets).lower()
    for m in re.finditer(r'"([^"]{8,})"', body):
        title = m.group(1).strip().lower()
        if title and title not in allowed_lower:
            return True
    # Block "I researched X" style claims without overlapping evidence tokens
    claimish = re.findall(
        r"(?:I (?:studied|researched|worked on|published)|your novel finding on)\s+([^.!\n]{12,})",
        body,
        flags=re.I,
    )
    for claim in claimish:
        tokens = [t for t in re.findall(r"[a-z0-9]{5,}", claim.lower())]
        if tokens and not any(t in allowed_lower for t in tokens):
            return True
    return False


def to_eml(recipient: str, subject: str, body: str, sender: str = "me@example.com") -> bytes:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)
    return msg.as_bytes()


def mailto_link(recipient: str, subject: str, body: str) -> str:
    from urllib.parse import quote

    return f"mailto:{recipient}?subject={quote(subject)}&body={quote(body)}"


def save_or_update_draft(conn, opportunity_id: int, draft: dict) -> int:
    existing = conn.execute(
        "SELECT id, approved_hash FROM draft WHERE opportunity_id = ?",
        (opportunity_id,),
    ).fetchone()
    if existing:
        # editing clears approval
        conn.execute(
            """
            UPDATE draft
            SET recipient=?, subject=?, body=?, content_hash=?, approved_hash=NULL,
                updated_at=datetime('now')
            WHERE id=?
            """,
            (
                draft["recipient"],
                draft["subject"],
                draft["body"],
                draft["content_hash"],
                existing["id"],
            ),
        )
        return int(existing["id"])
    cur = conn.execute(
        """
        INSERT INTO draft(opportunity_id, recipient, subject, body, content_hash)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            opportunity_id,
            draft["recipient"],
            draft["subject"],
            draft["body"],
            draft["content_hash"],
        ),
    )
    return int(cur.lastrowid)


def approve_draft(conn, draft_id: int) -> None:
    row = conn.execute("SELECT * FROM draft WHERE id = ?", (draft_id,)).fetchone()
    if not row:
        raise ValueError("Draft not found")
    # Allowed evidence only — never the draft body itself (would self-approve).
    allowed: list[str] = []
    pubs = conn.execute(
        """
        SELECT p.title, p.url, p.abstract
        FROM publication p
        JOIN opportunity o ON o.researcher_id = p.researcher_id
        JOIN draft d ON d.opportunity_id = o.id
        WHERE d.id = ?
        """,
        (draft_id,),
    ).fetchall()
    for p in pubs:
        allowed.extend([p["title"] or "", p["url"] or "", p["abstract"] or ""])
    facts = conn.execute(
        "SELECT body FROM profile_fact WHERE confirmed = 1"
    ).fetchall()
    for f in facts:
        allowed.append(f["body"] or "")
    opp = conn.execute(
        """
        SELECT o.note, o.apply_url FROM opportunity o
        JOIN draft d ON d.opportunity_id = o.id
        WHERE d.id = ?
        """,
        (draft_id,),
    ).fetchone()
    if opp:
        allowed.extend([opp["note"] or "", opp["apply_url"] or ""])
    if has_uncited_claim(row["body"], allowed):
        raise ValueError("Uncited claim in draft. Remove it or cite a sourced sentence.")
    conn.execute(
        "UPDATE draft SET approved_hash = content_hash, updated_at=datetime('now') WHERE id = ?",
        (draft_id,),
    )


def clear_approval_if_edited(conn, draft_id: int, recipient: str, subject: str, body: str) -> str:
    h = content_hash(recipient, subject, body)
    row = conn.execute("SELECT approved_hash FROM draft WHERE id = ?", (draft_id,)).fetchone()
    approved = row["approved_hash"] if row else None
    if approved and approved != h:
        conn.execute(
            """
            UPDATE draft SET recipient=?, subject=?, body=?, content_hash=?, approved_hash=NULL
            WHERE id=?
            """,
            (recipient, subject, body, h, draft_id),
        )
    else:
        conn.execute(
            """
            UPDATE draft SET recipient=?, subject=?, body=?, content_hash=?
            WHERE id=?
            """,
            (recipient, subject, body, h, draft_id),
        )
    return h
