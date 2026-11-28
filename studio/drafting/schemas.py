"""Structured drafting schemas (Pydantic)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


StrategyName = Literal[
    "research_alignment",
    "technical_contribution",
    "publication_led",
    "research_extension",
    "learning_oriented",
    "advertised_opening",
    "collaboration_inquiry",
    "phd_inquiry",
    "follow_up",
    "referral",
]


class EvidenceItem(BaseModel):
    id: str
    statement: str
    source: str = ""
    url: str = ""
    kind: Literal[
        "student_project",
        "student_skill",
        "student_interest",
        "student_coursework",
        "faculty_publication",
        "faculty_note",
        "opportunity",
    ]
    verified: bool = True
    relevance: float = 0.0
    permitted_in_email: bool = True


class DraftSection(BaseModel):
    role: str
    text: str
    evidence_ids: list[str] = Field(default_factory=list)


class StructuredDraft(BaseModel):
    strategy: StrategyName
    subject: str
    sections: list[DraftSection]
    tone: str = "professional"
    length: str = "balanced"


class WritingPreferences(BaseModel):
    intent: str = "summer_internship"
    tone: Literal["professional", "academic", "direct", "conversational"] = "professional"
    length: Literal["concise", "balanced", "detailed"] = "balanced"
    emphasis: str = "research_alignment"
