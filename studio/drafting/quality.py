"""Application Quality Inspector — specific checks, not a generic polish button."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from studio.drafting.evidence import EvidenceItem
from studio.drafts import has_hard_evidence_violation


@dataclass
class QualityCheck:
    id: str
    label: str
    status: str  # pass | warn | fail
    detail: str


@dataclass
class QualityReport:
    checks: list[QualityCheck] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    hard_fail: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "checks": [asdict(c) for c in self.checks],
            "improvements": self.improvements,
            "hard_fail": self.hard_fail,
        }


def inspect_application_quality(
    *,
    subject: str,
    body: str,
    researcher_name: str,
    institution: str | None,
    evidence: list[EvidenceItem],
    opportunity: dict[str, Any] | None = None,
    already_contacted: bool = False,
) -> QualityReport:
    report = QualityReport()
    allow = [e.statement for e in evidence] + [e.source for e in evidence] + [e.url for e in evidence]
    allow += [researcher_name, institution or ""]

    # Faculty identity
    first = (researcher_name or "").split()[0]
    if first and first.lower() in body.lower():
        report.checks.append(QualityCheck("faculty_identity", "Faculty identity", "pass", "Name appears in the letter."))
    else:
        report.checks.append(QualityCheck("faculty_identity", "Faculty identity", "warn", "Recipient name not found in body."))

    # Publication references
    pub_urls = [e.url for e in evidence if e.kind == "faculty_publication" and e.url]
    body_urls = [u.rstrip(").,") for u in re.findall(r"https?://\S+", body)]
    unknown = [u for u in body_urls if not any(u in (a or "") for a in allow)]
    if unknown:
        report.checks.append(
            QualityCheck("publications", "Publication references", "fail", f"Unknown URL(s): {', '.join(unknown[:2])}")
        )
        report.hard_fail = True
    elif pub_urls or any(e.kind == "faculty_publication" for e in evidence):
        report.checks.append(
            QualityCheck("publications", "Publication references", "pass", "Faculty research references are sourced.")
        )
    else:
        report.checks.append(
            QualityCheck("publications", "Publication references", "warn", "No faculty publication evidence attached.")
        )

    # Student achievements — mandatory evidence only for the inspector hard-fail path.
    # Inventiveness (≥5 novel tokens) is reserved for AI rewrite guards, not offline templates.
    if has_hard_evidence_violation(body, allow):
        report.checks.append(
            QualityCheck(
                "student",
                "Student achievements",
                "fail",
                "Unsupported claim or URL not grounded in approved evidence.",
            )
        )
        report.hard_fail = True
    else:
        report.checks.append(
            QualityCheck(
                "student",
                "Student achievements",
                "pass",
                "Claims are grounded in approved evidence.",
            )
        )

    # Research connection specificity
    student_tokens = set()
    for e in evidence:
        if e.kind.startswith("student_"):
            student_tokens |= set(re.findall(r"[a-z]{5,}", e.statement.lower()))
    overlap = [t for t in student_tokens if t in body.lower()]
    if len(overlap) >= 2:
        report.checks.append(
            QualityCheck("connection", "Research connection", "pass", "Specific student evidence appears in prose.")
        )
    else:
        report.checks.append(
            QualityCheck("connection", "Research connection", "warn", "Connection may be generic — strengthen with confirmed evidence.")
        )
        report.improvements.append("Strengthen research connection")

    # Funding claims
    if re.search(r"\b(fully funded|guaranteed funding|funded opening is confirmed)\b", body, re.I):
        fund = ((opportunity or {}).get("funding") or "").lower()
        if fund not in {"stated-yes", "yes"}:
            report.checks.append(
                QualityCheck("funding", "Funding claims", "fail", "Funding asserted without catalog support.")
            )
            report.hard_fail = True
        else:
            report.checks.append(QualityCheck("funding", "Funding claims", "pass", "Funding claim matches catalog."))
    else:
        report.checks.append(QualityCheck("funding", "Funding claims", "pass", "None asserted."))

    # Recruitment
    status = ((opportunity or {}).get("status") or "unknown").lower()
    if status in {"stated-no", "closed"}:
        report.checks.append(
            QualityCheck("recruitment", "Recruitment status", "warn", "Catalog marks not recruiting — confirm before sending.")
        )
    elif status in {"stated-yes", "open"}:
        report.checks.append(QualityCheck("recruitment", "Recruitment status", "pass", "Opening recorded in catalog."))
    else:
        report.checks.append(
            QualityCheck("recruitment", "Recruitment status", "warn", "Unconfirmed — do not imply a vacancy.")
        )

    # Duplicate
    if already_contacted:
        report.checks.append(
            QualityCheck("duplicate", "Prior correspondence", "fail", "Already contacted this researcher.")
        )
        report.hard_fail = True
    else:
        report.checks.append(
            QualityCheck("duplicate", "Prior correspondence", "pass", "No duplicate detected.")
        )

    # Length / generic language
    words = len(re.findall(r"\w+", body))
    if words > 350:
        report.improvements.append("Make more concise")
    if re.search(r"I am writing to express my (?:keen )?interest", body, re.I):
        report.improvements.append("Remove generic language")
    if not re.search(r"\b(would|appreciate|discuss|contribute|opportunity)\b", body, re.I):
        report.improvements.append("Clarify the request")

    report.improvements = list(dict.fromkeys(report.improvements))
    return report
