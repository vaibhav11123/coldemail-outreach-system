"""Redistributable preview sample (xlsx + csv) for marketplace listings.

Rows are real catalog records, unmodified. Nothing is invented, and the sample
carries no customer fingerprint: Export IDs are plain ordinals (SAMPLE-001, ...).
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any

from studio.dataset.records import FACTUAL_FIELDS
from studio.dataset.workbook import build_workbook, save_workbook

SAMPLE_COLUMNS = ("export_id",) + FACTUAL_FIELDS
SAMPLE_XLSX = "GlobalResearch_SAMPLE.xlsx"
SAMPLE_CSV = "GlobalResearch_SAMPLE.csv"
SAMPLE_README = "README_SAMPLE.txt"
DEFAULT_SAMPLE_SIZE = 25

# Fields that a representative preview row should have.
_CORE_FIELDS = ("display_name", "university", "email", "paper_title")


def _filled(rec: dict[str, Any], field: str) -> bool:
    return bool(str(rec.get(field) or "").strip())


def select_sample_records(
    records: list[dict[str, Any]], n: int = DEFAULT_SAMPLE_SIZE
) -> list[dict[str, Any]]:
    """First n records (input order) with the core fields filled.

    If fewer than n qualify, the remainder is filled with the most complete of
    the other records, again in input order. Never returns more than exist.
    """
    if n < 1:
        raise ValueError("sample size must be at least 1")
    complete = [r for r in records if all(_filled(r, f) for f in _CORE_FIELDS)]
    picked = complete[:n]
    if len(picked) < n:
        chosen = {id(r) for r in picked}
        rest = [r for r in records if id(r) not in chosen]
        ranked = sorted(
            enumerate(rest),
            key=lambda t: (-sum(_filled(t[1], f) for f in FACTUAL_FIELDS), t[0]),
        )
        picked.extend(r for _, r in ranked[: n - len(picked)])
    return picked


def _redact_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        return ""
    return f"{local[:1]}***@{domain}"


def write_sample_pack(
    records: list[dict[str, Any]],
    out_dir: Path,
    *,
    n: int = DEFAULT_SAMPLE_SIZE,
    packaged_on: date | None = None,
    redact_emails: bool = False,
) -> dict[str, Any]:
    """Write GlobalResearch_SAMPLE.xlsx/.csv/README under out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    packaged_on = packaged_on or date.today()
    chosen = select_sample_records(records, n)
    rows: list[dict[str, Any]] = []
    for i, rec in enumerate(chosen, start=1):
        row = {f: rec.get(f) for f in FACTUAL_FIELDS}
        row["export_id"] = f"SAMPLE-{i:03d}"
        row["canonical_id"] = row["export_id"]
        if redact_emails and row.get("email"):
            row["email"] = _redact_email(str(row["email"]))
        rows.append(row)

    banner = (
        f"Sample: {len(rows)} of {len(records)} records from the Global Research Dataset. "
        "Preview only; the purchased dataset is complete."
    )
    provenance = {
        "product": "Global Research Dataset",
        "kind": "sample",
        "sample_records": len(rows),
        "total_records": len(records),
        "notice": "Sample records are unmodified catalog rows with no customer fingerprint.",
    }
    wb = build_workbook(
        rows,
        banner=banner,
        provenance=provenance,
        packaged_on=packaged_on,
        title=f"Global Research Dataset {packaged_on.year} — Sample",
        sample_of=len(records),
    )
    xlsx = out_dir / SAMPLE_XLSX
    save_workbook(xlsx, wb)

    csv_path = out_dir / SAMPLE_CSV
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        f.write(f"# {banner}\n")
        writer = csv.DictWriter(f, fieldnames=list(SAMPLE_COLUMNS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in SAMPLE_COLUMNS})

    readme = out_dir / SAMPLE_README
    readme.write_text(
        f"{banner}\n\n"
        "Files\n"
        f"  {SAMPLE_XLSX}  workbook (start on the 'Start Here' sheet)\n"
        f"  {SAMPLE_CSV}   the same rows as CSV (raw status tokens)\n\n"
        "Rows are unmodified catalog records selected because their core fields "
        "(name, university, email, paper title) are filled. Nothing was added or "
        "edited. Completeness figures in the workbook describe this sample only, "
        "not the full dataset.\n"
        + (
            "Email addresses are partially masked in this sample.\n"
            if redact_emails
            else ""
        ),
        encoding="utf-8",
    )
    return {
        "out_dir": str(out_dir),
        "sample_records": len(rows),
        "total_records": len(records),
        "files": [SAMPLE_XLSX, SAMPLE_CSV, SAMPLE_README],
    }
