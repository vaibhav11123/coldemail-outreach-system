"""Deterministic offline composition — strategy-aware templates, no AI required."""

from __future__ import annotations

import hashlib
import re

from studio.drafting.schemas import EvidenceItem, StrategyName, StructuredDraft, WritingPreferences


def _content_hash(recipient: str, subject: str, body: str) -> str:
    return hashlib.sha256(f"{recipient}\n{subject}\n{body}".encode()).hexdigest()


def _student_name(evidence: list[EvidenceItem]) -> str:
    for e in evidence:
        if e.kind == "student_name" and e.statement:
            return e.statement.strip()
    # Strip leading "Name - " patterns from project lines without embedding them mid-sentence
    return ""


def _clean_student_line(statement: str, student_name: str) -> str:
    text = (statement or "").strip()
    if not text:
        return "my coursework and research interests"
    if student_name and text.lower().startswith(student_name.lower()):
        text = re.sub(r"^[^—\-–:]+[—\-–:]\s*", "", text).strip()
    # Drop internal field labels that leaked into profile facts
    text = re.sub(
        r"^(?:My relevant experience|Looking for|Relevant experience)\s*:\s*",
        "",
        text,
        flags=re.I,
    ).strip()
    return text or "my coursework and research interests"


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
    if first and first.lower() not in {"professor", "dr", "dr."}:
        greeting = f"Dear Professor {first}"
    else:
        greeting = "Dear Professor"
    student = [e for e in evidence if e.kind.startswith("student_")]
    faculty = [e for e in evidence if e.kind.startswith("faculty_")]
    signature = _student_name(evidence)
    student_line = _clean_student_line(
        student[0].statement if student else "",
        signature,
    )
    faculty_line = faculty[0].source or faculty[0].statement if faculty else "your research"
    faculty_url = faculty[0].url if faculty else ""
    sig_block = f"\n\nBest regards,\n{signature}" if signature else "\n\nBest regards,"

    if strategy == "learning_oriented":
        subject = f"Research inquiry — learning-focused interest in {faculty_line[:50]}"
        intro = (
            f"{greeting},\n\n"
            f"I am interested in developing research skills related to your work on {faculty_line}. "
        )
        mid = (
            f"My preparation includes {student_line}. "
            f"I do not yet have a completed research project in this area, but I am looking for a "
            f"structured opportunity to contribute carefully under guidance. "
        )
        close = (
            "If you are open to undergraduate researchers, I would appreciate any advice on how "
            "to prepare a stronger application to your group."
        )
    elif strategy == "advertised_opening":
        subject = f"Summer 2027 research inquiry — {faculty_line[:55]}"
        intro = (
            f"{greeting},\n\n"
            f"I am interested in exploring research opportunities connected with your work on {faculty_line}. "
        )
        mid = (
            f"My recent projects include {student_line}. "
            f"Your research particularly interests me because I would like to contribute carefully "
            f"to an ongoing project in this area. "
        )
        close = (
            "I would welcome the chance to discuss whether my background fits an opening in your group."
        )
    elif strategy == "technical_contribution":
        subject = "Summer research inquiry — systems contribution"
        intro = (
            f"{greeting},\n\n"
            f"I am interested in the systems challenges behind efficient research software. "
        )
        mid = (
            f"Recently I have worked on {student_line}. "
            f"This direction relates to your group's focus on {faculty_line}. "
        )
        close = (
            "I would like to contribute to an ongoing project this summer if you are considering "
            "undergraduate researchers."
        )
    else:  # research_alignment / publication_led / default
        subject = f"Research internship inquiry — {faculty_line[:55]}"
        intro = (
            f"{greeting},\n\n"
            f"I am writing to explore research opportunities related to {faculty_line}. "
        )
        mid = (
            f"My background includes {student_line}. "
            f"I see a concrete connection between this experience and the themes in your publications. "
        )
        close = (
            "If you are open to discussing undergraduate research, I would appreciate the opportunity "
            "to learn where I might be useful."
        )

    if prefs.length == "concise":
        body = intro + mid + close + sig_block
    elif prefs.length == "detailed":
        cite = f" (source on file{': ' + faculty_url if faculty_url else ''})" if faculty else ""
        body = intro + mid + f"I have reviewed the available lab materials{cite}. " + close + sig_block
    else:
        body = intro + mid + close + sig_block

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
