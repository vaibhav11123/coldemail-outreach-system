"""Public-web piracy monitoring scaffold.

Compares discovered artefacts against the delivery ledger. Hits are candidates for
human review — never automatic customer accusation (theft from a buyer is possible).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from studio.licensing.ledger import DeliveryLedger

PRODUCT_MARKERS = (
    "Global Research Faculty Dataset",
    "ResearchCatalog.asdb",
    "CustomerLicense.aslic",
    "Academic Outreach Studio",
    "Academic Data Reader",
    "faculty_catalog.xlsx",
)

EXPORT_ID_RE = re.compile(r"\bR-[0-9A-F]{8}\b")
HASHABLE_SUFFIXES = {".csv", ".json", ".txt", ".md", ".html", ".aslic"}
HASHABLE_NAMES = {
    "faculty_catalog.csv",
    "faculty_catalog.json",
    "manifest.json",
    "ResearchCatalog.asdb",
    "ResearchCatalog.aspkg",
}


@dataclass
class MonitorFinding:
    source: str
    url: str | None
    matched_markers: list[str]
    export_ids: list[str]
    file_hashes: list[str]
    ledger_hits: list[dict[str, Any]] = field(default_factory=list)
    notes: str = ""
    discovered_at: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def extract_signals(text: str) -> tuple[list[str], list[str]]:
    markers = [m for m in PRODUCT_MARKERS if m.lower() in text.lower()]
    export_ids = sorted(set(EXPORT_ID_RE.findall(text)))
    return markers, export_ids


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def evaluate_public_text(
    *,
    source: str,
    text: str,
    ledger: DeliveryLedger,
    url: str | None = None,
    file_hashes: list[str] | None = None,
) -> MonitorFinding | None:
    markers, export_ids = extract_signals(text)
    hashes = list(file_hashes or [])
    if not markers and not export_ids and not hashes:
        return None
    ledger_hits: list[dict[str, Any]] = []
    if export_ids:
        ledger_hits.extend(ledger.find_by_export_ids(export_ids))
    for h in hashes:
        ledger_hits.extend(ledger.find_by_file_hash(h))
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for hit in ledger_hits:
        key = str(hit.get("delivery_id") or json.dumps(hit, sort_keys=True, default=str))
        if key in seen:
            continue
        seen.add(key)
        unique.append(hit)
    return MonitorFinding(
        source=source,
        url=url,
        matched_markers=markers,
        export_ids=export_ids,
        file_hashes=hashes,
        ledger_hits=unique,
        notes=(
            "Candidate only — preserve evidence and review manually before "
            "takedown or contacting a customer."
        ),
        discovered_at=int(time.time()),
    )


def scan_local_corpus(paths: list[Path], ledger: DeliveryLedger) -> list[MonitorFinding]:
    """Offline stand-in for crawlers: scan local files/folders for markers."""
    findings: list[MonitorFinding] = []
    for path in paths:
        if not path.exists():
            continue
        files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()]
        for f in files:
            if f.stat().st_size > 8_000_000:
                continue
            hashes: list[str] = []
            if f.name in HASHABLE_NAMES and f.stat().st_size <= 8_000_000:
                hashes.append(sha256_hex(f.read_bytes()))
            text = f.name
            if f.suffix.lower() in HASHABLE_SUFFIXES and f.stat().st_size <= 2_000_000:
                try:
                    text = f"{f.name}\n" + f.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    pass
            finding = evaluate_public_text(
                source="local_corpus",
                text=text,
                ledger=ledger,
                url=str(f),
                file_hashes=hashes,
            )
            if finding:
                findings.append(finding)
    return findings


def append_findings_log(path: Path, findings: list[MonitorFinding]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict] = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = []
    existing.extend(f.to_dict() for f in findings)
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")


def is_plausible_public_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(
        host == domain or host.endswith("." + domain)
        for domain in (
            "github.com",
            "githubusercontent.com",
            "gumroad.com",
            "reddit.com",
            "t.me",
            "telegram.me",
        )
    )
