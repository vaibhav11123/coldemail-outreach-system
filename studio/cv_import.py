"""CV-first onboarding: local PDF/DOCX/TXT extraction → editable profile facts.

CV bytes stay on device. Optional AI enhancement only if the customer already
connected a provider and explicitly opts in later.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


class ExtractedProfile(BaseModel):
    interests: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    coursework: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    raw_preview: str = ""
    warnings: list[str] = Field(default_factory=list)


@dataclass
class CvParseResult:
    text: str
    profile: ExtractedProfile
    source_format: str


URL_RE = re.compile(r"https?://\S+|github\.com/\S+|linkedin\.com/\S+", re.I)
SKILL_HINTS = re.compile(
    r"\b(python|c\+\+|rust|java|pytorch|tensorflow|cuda|sql|linux|git|"
    r"compiler|kernel|distributed|ml|machine learning|deep learning|"
    r"systems|networking|robotics|nlp|computer vision)\b",
    re.I,
)
SECTION_HEADERS = re.compile(
    r"^(education|experience|projects?|skills?|research|publications?|"
    r"coursework|interests?|objective|summary)\b[:\s]*",
    re.I | re.M,
)


def extract_text_from_bytes(filename: str, data: bytes) -> tuple[str, str]:
    name = (filename or "").lower()
    if name.endswith(".pdf") or data[:4] == b"%PDF":
        return _pdf_text(data), "pdf"
    if name.endswith(".docx") or data[:2] == b"PK":
        # DOCX is a zip; try docx first, fall back to text
        try:
            return _docx_text(data), "docx"
        except Exception:
            pass
    try:
        return data.decode("utf-8"), "txt"
    except UnicodeDecodeError:
        return data.decode("latin-1", errors="replace"), "bin"


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts = []
    for page in reader.pages[:20]:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _docx_text(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def structure_cv_text(text: str) -> ExtractedProfile:
    warnings: list[str] = []
    if not text.strip():
        return ExtractedProfile(warnings=["No text could be extracted from this file."])
    if len(text.strip()) < 40:
        warnings.append("Extracted text is very short — confirm fields manually.")

    urls = [u.rstrip(").,") for u in URL_RE.findall(text)]
    skills = sorted({m.group(0) for m in SKILL_HINTS.finditer(text)}, key=str.lower)

    # Section-ish line harvesting
    interests: list[str] = []
    projects: list[str] = []
    coursework: list[str] = []
    current = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        header = SECTION_HEADERS.match(line)
        if header:
            current = header.group(1).lower()
            rest = line[header.end() :].strip(" :-")
            if rest:
                line = rest
            else:
                continue
        if current in {"interest", "interests", "objective", "summary", "research"}:
            if len(line) > 20:
                interests.append(line[:300])
        elif current in {"project", "projects", "experience"}:
            if len(line) > 20:
                projects.append(line[:400])
        elif current in {"coursework", "education"}:
            if len(line) > 8:
                coursework.append(line[:200])
        elif current in {"skill", "skills"}:
            for part in re.split(r"[,;/|•]", line):
                part = part.strip()
                if 2 < len(part) < 60:
                    skills.append(part)

    # Fallback: first substantial lines as interests if nothing sectioned
    if not interests:
        for line in text.splitlines():
            line = line.strip()
            if len(line) > 40 and not URL_RE.search(line):
                interests.append(line[:300])
                if len(interests) >= 3:
                    break

    # Deduplicate preserving order
    def uniq(items: list[str], cap: int) -> list[str]:
        seen = set()
        out = []
        for i in items:
            key = i.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(i)
            if len(out) >= cap:
                break
        return out

    return ExtractedProfile(
        interests=uniq(interests, 8),
        skills=uniq(skills, 24),
        projects=uniq(projects, 8),
        coursework=uniq(coursework, 12),
        urls=uniq(urls, 12),
        raw_preview=text[:1500],
        warnings=warnings,
    )


def parse_cv(filename: str, data: bytes) -> CvParseResult:
    text, fmt = extract_text_from_bytes(filename, data)
    profile = structure_cv_text(text)
    if fmt == "bin":
        profile.warnings.append("Unrecognized format; treated as plain text.")
    return CvParseResult(text=text, profile=profile, source_format=fmt)


def persist_extracted_profile(conn, profile: ExtractedProfile, *, confirmed: bool = False) -> int:
    """Insert unconfirmed facts for customer review (CV-first step 2)."""
    n = 0
    mapping = (
        ("interest", profile.interests),
        ("skill", profile.skills),
        ("project", profile.projects),
        ("coursework", profile.coursework),
    )
    flag = 1 if confirmed else 0
    for kind, items in mapping:
        for body in items:
            conn.execute(
                """
                INSERT INTO profile_fact(kind, body, source, confirmed)
                VALUES (?, ?, 'cv', ?)
                """,
                (kind, body, flag),
            )
            n += 1
    return n
