"""Deterministic offline composition — strategy-aware templates, no AI required."""

from __future__ import annotations

import hashlib

from studio.drafting.schemas import EvidenceItem, StrategyName, StructuredDraft, WritingPreferences


def _content_hash(recipient: str, subject: str, body: str) -> str:
    return hashlib.sha256(f"{recipient}\n{subject}\n{body}".encode()).hexdigest()


def deterministic_compose(
    *,
    researcher_name: str,
    recipient: str,
    strategy: StrategyName,
    evidence: list[EvidenceItem],
    prefs: WritingPreferences | None = None,
) -> dict:
    prefs = prefs or WritingPreferences()
    first = researcher_name.split()[0] if researcher_name else "Professor"
    student = [e for e in evidence if e.kind.startswith("student_")]
    faculty = [e for e in evidence if e.kind.startswith("faculty_")]
    student_line = student[0].statement if student else "my coursework and research interests"
    faculty_line = faculty[0].source or faculty[0].statement if faculty else "your research"
    faculty_url = faculty[0].url if faculty else ""

    # Internal evidence keeps URLs; recipient-facing prose stays URL-light
    if strategy == "learning_oriented":
        subject = f"Research inquiry — learning-focused interest in {faculty_line[:50]}"
        intro = (
            f"Dear {first},\n\n"
            f"I am an undergraduate developing skills in areas related to your work on {faculty_line}. "
        )
        mid = (
            f"My preparation includes {student_line}. "
            f"I do not yet have a completed research project in this area, but I am looking for a "
            f"structured opportunity to contribute carefully under guidance. "
        )
        close = (
            "If you are open to undergraduate researchers, I would appreciate any advice on how "
            "to prepare a stronger application to your group.\n\nBest regards,\n"
        )
    elif strategy == "advertised_opening":
        subject = f"Application interest — {faculty_line[:55]}"
        intro = (
            f"Dear {first},\n\n"
            f"I am writing regarding research opportunities connected with your work on {faculty_line}. "
        )
        mid = f"My relevant experience: {student_line}. "
        close = (
            "I would welcome the chance to discuss whether my background fits an opening in your group.\n\n"
            "Best regards,\n"
        )
    elif strategy == "technical_contribution":
        subject = f"Summer research inquiry — systems contribution"
        intro = (
            f"Dear {first},\n\n"
            f"I am interested in the systems challenges behind efficient research software. "
        )
        mid = (
            f"Recently I have worked on {student_line}. "
            f"This direction relates to your group's focus on {faculty_line}. "
        )
        close = (
            "I would like to contribute to an ongoing project this summer if you are considering "
            "undergraduate researchers.\n\nBest regards,\n"
        )
    else:  # research_alignment / publication_led / default
        subject = f"Research internship inquiry — {faculty_line[:55]}"
        intro = (
            f"Dear {first},\n\n"
            f"I am writing to explore research opportunities related to {faculty_line}. "
        )
        mid = (
            f"My background includes {student_line}. "
            f"I see a concrete connection between this experience and the themes in your publications. "
        )
        close = (
            "If you are open to discussing undergraduate research, I would appreciate the opportunity "
            "to learn where I might be useful.\n\nBest regards,\n"
        )

    if prefs.length == "concise":
        body = intro + mid + close
    elif prefs.length == "detailed":
        cite = f" (source on file{': ' + faculty_url if faculty_url else ''})" if faculty else ""
        body = intro + mid + f"I have reviewed the available lab materials{cite}. " + close
    else:
        body = intro + mid + close

    citations = []
    for e in evidence[:6]:
        citations.append(
            {
                "applicant": e.statement if e.kind.startswith("student_") else "",
                "source": e.source or e.statement,
                "url": e.url,
                "evidence_id": e.id,
            }
        )
    return {
        "recipient": recipient,
        "subject": subject[:180],
        "body": body,
        "content_hash": _content_hash(recipient, subject[:180], body),
        "citations": citations,
        "strategy": strategy,
        "evidence_ids": [e.id for e in evidence],
    }


def structured_from_deterministic(draft: dict, strategy: StrategyName) -> StructuredDraft:
    from studio.drafting.schemas import DraftSection

    return StructuredDraft(
        strategy=strategy,
        subject=draft["subject"],
        sections=[
            DraftSection(role="body", text=draft["body"], evidence_ids=draft.get("evidence_ids") or [])
        ],
    )
