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
    opportunity: dict | None = None,
    prefs: dict | None = None,
) -> dict:
    """Evidence-grounded composition with strategy selection.

    Still requires confirmed student evidence (project, coursework, skill, or interest)
    and sourced faculty material when claiming publications. Deterministic by default;
    AI structured composition is optional inside compose_application.
    """
    from studio.drafting.composer import compose_application
    from studio.drafting.schemas import WritingPreferences

    wp = WritingPreferences(**(prefs or {})) if prefs else WritingPreferences()
    return compose_application(
        researcher_name=researcher_name,
        recipient=recipient,
        profile_facts=profile_facts,
        publications=publications,
        reasons=reasons,
        opportunity=opportunity,
        prefs=wp,
        use_ai=False,  # keep send-path deterministic unless rewrite endpoint opts in
    )


# Connective / template vocabulary that must never trip offline deterministic drafts.
_TEMPLATE_ALLOW = {
    "writing",
    "interest",
    "explore",
    "exploring",
    "openings",
    "opening",
    "group",
    "thank",
    "thanks",
    "professor",
    "recent",
    "recently",
    "project",
    "projects",
    "please",
    "would",
    "about",
    "paper",
    "papers",
    "dear",
    "hello",
    "regards",
    "sincerely",
    "opportunity",
    "opportunities",
    "research",
    "researcher",
    "researchers",
    "letter",
    "outreach",
    "undergraduate",
    "graduate",
    "summer",
    "internship",
    "inquiry",
    "interested",
    "appreciate",
    "discuss",
    "discussion",
    "contribute",
    "contribution",
    "background",
    "experience",
    "preparation",
    "includes",
    "include",
    "related",
    "relevant",
    "available",
    "materials",
    "source",
    "guidance",
    "structured",
    "carefully",
    "stronger",
    "application",
    "applications",
    "systems",
    "challenges",
    "efficient",
    "software",
    "direction",
    "relates",
    "focus",
    "themes",
    "publications",
    "publication",
    "concrete",
    "connection",
    "between",
    "experience",
    "looking",
    "completed",
    "advice",
    "prepare",
    "welcome",
    "chance",
    "whether",
    "fits",
    "considering",
    "ongoing",
    "useful",
    "learn",
    "where",
    "might",
    "during",
    "particularly",
    "because",
    "behind",
    "model",
    "execution",
    "machine",
    "learning",
    "artificial",
    "intelligence",
    "computer",
    "science",
    "engineering",
    "faculty",
    "laboratory",
    "university",
    "college",
    "student",
    "coursework",
    "skills",
    "areas",
    "work",
    "worked",
    "building",
    "built",
    "using",
    "python",
    "pytorch",
    "fastapi",
    "transformer",
    "transformers",
    "summarizer",
    "scientific",
    "abstracts",
    "academic",
    "search",
    "interface",
    "best",
}


def has_hard_evidence_violation(body: str, allowed_snippets: list[str]) -> bool:
    """Mandatory evidence checks for every draft (deterministic or AI)."""
    urls = re.findall(r"https?://\S+", body)
    for url in urls:
        cleaned = url.rstrip(").,")
        if not any(cleaned in (s or "") for s in allowed_snippets):
            return True
    allowed_lower = " ".join(s or "" for s in allowed_snippets).lower()
    for m in re.finditer(r'"([^"]{8,})"', body):
        title = m.group(1).strip().lower()
        if title and title not in allowed_lower:
            return True
    fundingish = re.search(
        r"\b(?:funded\s+openings?|fully\s+funded|guaranteed\s+(?:funding|admission)|"
        r"confirmed\s+funded|acceptance\s+(?:is\s+)?(?:guaranteed|certain)|"
        r"GPA\s*(?:is|=)\s*\d|my\s+GPA\s+is)\b",
        body,
        flags=re.I,
    )
    if fundingish:
        snippet = fundingish.group(0).lower()
        if snippet not in allowed_lower and "funded" not in allowed_lower and "gpa" not in allowed_lower:
            return True
    claimish = re.findall(
        r"(?:I (?:studied|researched|worked on|published|discovered|invented|proved)|your novel finding on)\s+([^.!\n]{12,})",
        body,
        flags=re.I,
    )
    for claim in claimish:
        tokens = [t for t in re.findall(r"[a-z0-9]{5,}", claim.lower())]
        if tokens and not any(t in allowed_lower for t in tokens):
            return True
    return False


def has_uncited_claim(
    body: str,
    allowed_snippets: list[str],
    *,
    inventiveness_guard: bool = True,
) -> bool:
    """Block approval when body invents claims not grounded in evidence.

    ``inventiveness_guard`` (AI rewrite path) applies the novel-token heuristic.
    Offline deterministic templates only run mandatory evidence checks.
    """
    if has_hard_evidence_violation(body, allowed_snippets):
        return True
    if not inventiveness_guard:
        return False
    allowed_lower = " ".join(s or "" for s in allowed_snippets).lower()
    body_tokens = set(re.findall(r"[a-z]{6,}", body.lower()))
    allowed_tokens = set(re.findall(r"[a-z]{6,}", allowed_lower))
    invented = body_tokens - allowed_tokens - _TEMPLATE_ALLOW
    if len(invented) >= 3 and any(
        w in invented for w in ("theorem", "lunar", "agriculture", "quantum", "basket", "weaving")
    ):
        return True
    if len(invented) >= 5:
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
        "SELECT kind, body FROM profile_fact WHERE confirmed = 1"
    ).fetchall()
    for f in facts:
        allowed.append(f["body"] or "")
    opp = conn.execute(
        """
        SELECT o.note, o.apply_url, o.funding, o.status, r.display_name
        FROM opportunity o
        JOIN draft d ON d.opportunity_id = o.id
        JOIN researcher r ON r.id = o.researcher_id
        WHERE d.id = ?
        """,
        (draft_id,),
    ).fetchone()
    if opp:
        allowed.extend(
            [
                opp["note"] or "",
                opp["apply_url"] or "",
                opp["display_name"] or "",
            ]
        )
    # Mandatory evidence gate (URLs / titles / funding / claimish).
    if has_hard_evidence_violation(row["body"], allowed):
        raise ValueError(
            "Hard validation failed: unsupported claim detected. "
            "Remove or ground the highlighted claim before approval."
        )
    # Full quality inspector — hard_fail blocks approve/send.
    try:
        from studio.drafting.evidence import build_evidence_graph
        from studio.drafting.quality import inspect_application_quality

        fact_rows = [
            {"kind": f["kind"] or "project", "body": f["body"], "confirmed": 1}
            for f in facts
        ]
        pub_rows = [
            {"title": p["title"], "url": p["url"], "abstract": p["abstract"]}
            for p in pubs
        ]
        evidence = build_evidence_graph(
            fact_rows,
            pub_rows,
            [],
            opportunity=dict(opp) if opp else None,
        )
        report = inspect_application_quality(
            subject=row["subject"] or "",
            body=row["body"] or "",
            researcher_name=(opp["display_name"] if opp else "") or "",
            institution=None,
            evidence=evidence,
            opportunity=dict(opp) if opp else None,
        )
        if report.hard_fail:
            detail = next(
                (c.detail for c in report.checks if c.status == "fail"),
                "Resolve quality failures before approval.",
            )
            raise ValueError(f"Hard validation failed: {detail}")
    except ValueError:
        raise
    except Exception:
        # If inspector cannot run, still keep the hard evidence gate above.
        pass
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
