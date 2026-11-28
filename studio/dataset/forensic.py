"""Internal forensic inspection for suspected leaked packages.

Never auto-accuse a customer from a fingerprint match alone. Report evidence,
confidence, conflicts, and attribution limitations for human review.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from studio.licensing.ledger import DeliveryLedger

EXPORT_ID_RE = re.compile(r"\bR-[0-9A-F]{8}\b")
HASH_NAMES = {
    "faculty_catalog.csv",
    "faculty_catalog.json",
    "faculty_catalog.xlsx",
    "manifest.json",
    "ResearchCatalog.asdb",
    "ResearchCatalog.aspkg",
    "CustomerLicense.aslic",
}


@dataclass
class ForensicReport:
    path: str
    matched_export_ids: list[str] = field(default_factory=list)
    file_hashes: dict[str, str] = field(default_factory=dict)
    surviving_fingerprints: list[str] = field(default_factory=list)
    detected_transformations: list[str] = field(default_factory=list)
    ledger_hits: list[dict[str, Any]] = field(default_factory=list)
    attribution_confidence: str = "none"  # none | low | medium | high
    conflicting_evidence: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect_text_ids(text: str) -> list[str]:
    return sorted(set(EXPORT_ID_RE.findall(text)))


def _scan_tree(root: Path) -> tuple[list[str], dict[str, str], list[str]]:
    ids: set[str] = set()
    hashes: dict[str, str] = {}
    transforms: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        name = path.name
        if name in HASH_NAMES or path.suffix.lower() in {".csv", ".json", ".xlsx", ".asdb", ".aspkg", ".aslic"}:
            hashes[str(path.relative_to(root))] = _sha256_file(path)
        if path.suffix.lower() in {".csv", ".json", ".txt", ".md", ".html"}:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            ids.update(_collect_text_ids(text))
            if name.endswith(".csv") and "export_id" not in text[:2000].lower():
                transforms.append(f"csv_missing_export_id_header:{path.name}")
        if name.lower() == "manifest.json":
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for key in ("customer_id", "license_id", "delivery_id"):
                        if data.get(key):
                            ids.add(str(data[key]))
            except (OSError, json.JSONDecodeError):
                transforms.append(f"manifest_unreadable:{path.name}")
    return sorted(ids), hashes, transforms


def inspect_path(path: Path, ledger: DeliveryLedger | None = None) -> ForensicReport:
    path = path.resolve()
    report = ForensicReport(path=str(path))
    report.limitations = [
        "Fingerprint match is not automatic proof of piracy; theft from a buyer is possible.",
        "Sorted CSV loses row-order fingerprint; export IDs may still survive.",
        "Stripped XLSX metadata may remove workbook provenance while export IDs remain.",
        "Partial extracts may leave insufficient identifiers for high-confidence attribution.",
        "Combining multiple customer datasets can confuse single-customer attribution.",
    ]

    work = path
    tmp_extract: Path | None = None
    if path.is_file() and path.suffix.lower() == ".zip":
        tmp_extract = path.parent / f".forensic-extract-{path.stem}"
        tmp_extract.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "r") as zf:
            zf.extractall(tmp_extract)
        work = tmp_extract
        report.notes.append("Inspected zip by extracting to a temporary directory.")
    elif path.is_file():
        # Single file
        if path.suffix.lower() in {".csv", ".json", ".txt", ".md", ".html"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            report.matched_export_ids = _collect_text_ids(text)
        report.file_hashes[path.name] = _sha256_file(path)
        work = path.parent

    if path.is_dir() or (tmp_extract and tmp_extract.is_dir()):
        ids, hashes, transforms = _scan_tree(work if path.is_dir() or tmp_extract else path.parent)
        report.matched_export_ids = sorted(set(report.matched_export_ids) | set(ids))
        report.file_hashes.update(hashes)
        report.detected_transformations.extend(transforms)

    # Treat R-######## as surviving fingerprint signals
    report.surviving_fingerprints = [i for i in report.matched_export_ids if i.startswith("R-")]

    if ledger is not None and report.surviving_fingerprints:
        report.ledger_hits = ledger.find_by_export_ids(report.surviving_fingerprints)

    customers = {h.get("customer_id") for h in report.ledger_hits if h.get("customer_id")}
    if len(customers) > 1:
        report.conflicting_evidence.append(
            f"Export IDs match multiple customers: {sorted(customers)}"
        )
        report.attribution_confidence = "low"
    elif len(customers) == 1 and len(report.surviving_fingerprints) >= 3:
        report.attribution_confidence = "high"
        report.notes.append(
            "Multiple surviving export IDs map to one delivery — strong candidate for review."
        )
    elif len(customers) == 1:
        report.attribution_confidence = "medium"
        report.notes.append("At least one export ID maps to a delivery — human review required.")
    elif report.file_hashes and not report.surviving_fingerprints:
        report.attribution_confidence = "low"
        report.notes.append("File hashes available but no customer export IDs recovered.")
    else:
        report.attribution_confidence = "none"

    report.notes.append(
        "Do not accuse a customer solely because a fingerprint matches their purchase."
    )
    return report
