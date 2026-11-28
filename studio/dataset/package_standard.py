"""Standard Dataset: personalized Excel, CSV, JSON, SQLite with forensic fingerprints."""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from studio.dataset.fingerprint import (
    FingerprintContext,
    export_id_for,
    permute_rows,
    provenance_payload,
    visible_licence_banner,
)
from studio.dataset.records import FACTUAL_FIELDS, attach_export_ids
from studio.dataset.workbook import (
    SHEET_CHANGELOG,
    SHEET_COVERAGE,
    SHEET_DICTIONARY,
    SHEET_FACULTY,
    SHEET_PUBLICATIONS,
    SHEET_QUALITY,
    SHEET_SOURCES,
    SHEET_START,
    build_workbook,
    data_dictionary_text,
    save_workbook,
)
from studio.licensing.crypto import IssuerKeys, sign_ed25519
from studio.licensing.ledger import DeliveryLedger, sha256_bytes, sha256_file
from studio.licensing.products import SKU
from studio.paths import PACKAGE_ROOT


EXPORT_COLUMNS = ("export_id",) + FACTUAL_FIELDS

DATA_DICTIONARY = data_dictionary_text()


WORKBOOK_SHEET_GUIDE = "\n".join(
    f"  - {name}: {purpose}"
    for name, purpose in (
        (SHEET_START, "counts, navigation and how to use the workbook"),
        (SHEET_COVERAGE, "universities, research-area hints, completeness"),
        (SHEET_FACULTY, "every faculty record as a filterable table"),
        (SHEET_PUBLICATIONS, "representative papers (if packaged)"),
        (SHEET_SOURCES, "unique application and paper URLs (if packaged)"),
        (SHEET_DICTIONARY, "column meanings and how blanks are written"),
        (SHEET_QUALITY, "completeness, freshness and known limits"),
        (SHEET_CHANGELOG, "packaging date and record count"),
    )
)


def write_sqlite(path: Path, rows: list[dict[str, Any]], provenance: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(str(path))
    try:
        cols = list(EXPORT_COLUMNS)
        col_sql = ", ".join(f'"{c}" TEXT' for c in cols)
        conn.execute(f"CREATE TABLE faculty ({col_sql})")
        placeholders = ", ".join("?" for _ in cols)
        conn.executemany(
            f'INSERT INTO faculty ({", ".join(cols)}) VALUES ({placeholders})',
            [[str(row.get(c) or "") for c in cols] for row in rows],
        )
        conn.execute(
            "CREATE TABLE provenance (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.executemany(
            "INSERT INTO provenance(key, value) VALUES (?, ?)",
            [(str(k), str(v)) for k, v in provenance.items()],
        )
        conn.commit()
    finally:
        conn.close()


def write_customer_docs(
    out_dir: Path,
    *,
    ctx: FingerprintContext,
    customer_email: str | None,
    record_count: int,
    banner: str,
) -> list[str]:
    """Customer-facing documents (no issuer secrets, no operator receipts)."""
    written: list[str] = []
    start = out_dir / "START_HERE.txt"
    start.write_text(
        "Global Research Dataset — start here\n"
        "====================================\n\n"
        f"{banner}\n\n"
        f"Licensed to: {customer_email or ctx.customer_id}\n"
        f"Licence id: {ctx.license_id}\n"
        f"Records in this delivery: {record_count}\n\n"
        "Open GlobalResearch.xlsx (or faculty_catalog.xlsx) in Excel/LibreOffice.\n"
        "The workbook opens on the 'Start Here' sheet. Its sheets:\n"
        f"{WORKBOOK_SHEET_GUIDE}\n"
        "Publications and Sources appear only when the data contains papers or URLs.\n"
        "CSV/, JSON/, and SQLite copies contain the same factual fields.\n"
        "Read LICENSE.txt and Data_Dictionary.txt before sharing anything.\n\n"
        "Delivery is personalized. Do not upload this folder to public drives.\n"
        "Support: see LICENSE.txt / purchase confirmation email.\n"
        "Typical fulfilment SLA after payment clears: within 24 hours on business days.\n",
        encoding="utf-8",
    )
    written.append(start.name)

    licence_src = PACKAGE_ROOT / "legal" / "LICENCE_INDIVIDUAL.md"
    licence_txt = out_dir / "LICENSE.txt"
    if licence_src.exists():
        licence_txt.write_text(licence_src.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        licence_txt.write_text(
            "Individual perpetual licence included in purchase. See seller documentation.\n",
            encoding="utf-8",
        )
    written.append(licence_txt.name)

    dictionary = out_dir / "Data_Dictionary.txt"
    dictionary.write_text(DATA_DICTIONARY, encoding="utf-8")
    written.append(dictionary.name)

    # Stable alias expected by marketplace copy / docs
    xlsx = out_dir / "faculty_catalog.xlsx"
    alias = out_dir / "GlobalResearch.xlsx"
    if xlsx.exists() and not alias.exists():
        alias.write_bytes(xlsx.read_bytes())
        written.append(alias.name)
    return written


def build_export_id_map(
    records: list[dict[str, Any]], ctx: FingerprintContext
) -> dict[str, str]:
    return {r["canonical_id"]: export_id_for(ctx, r["canonical_id"]) for r in records}


def write_csv(path: Path, rows: list[dict[str, Any]], banner: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(f"# {banner}\n")
        writer = csv.DictWriter(f, fieldnames=list(EXPORT_COLUMNS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in EXPORT_COLUMNS})


def write_json(path: Path, rows: list[dict[str, Any]], provenance: dict) -> None:
    doc = {
        "provenance": provenance,
        "record_count": len(rows),
        "records": [{k: r.get(k) for k in EXPORT_COLUMNS} for r in rows],
    }
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def write_xlsx(
    path: Path,
    rows: list[dict[str, Any]],
    banner: str,
    provenance: dict,
    *,
    packaged_on: date | None = None,
    sample_of: int | None = None,
) -> None:
    """Write the customer workbook (Start Here, Coverage, Faculty Directory, ...).

    Data sheets (Publications, Sources) exist only when the rows support them.
    The Provenance sheet stays hidden.
    """
    wb = build_workbook(
        rows,
        banner=banner,
        provenance=provenance,
        packaged_on=packaged_on,
        sample_of=sample_of,
    )
    save_workbook(path, wb)


def write_manifest(
    path: Path,
    *,
    ctx: FingerprintContext,
    delivery_id: str,
    file_hashes: dict[str, str],
    record_count: int,
    issuer: IssuerKeys,
) -> tuple[dict, bytes]:
    manifest = {
        "format": "academic-studio-delivery-manifest",
        "version": 1,
        "sku": SKU.STANDARD_DATASET.value,
        "customer_id": ctx.customer_id,
        "license_id": ctx.license_id,
        "delivery_id": delivery_id,
        "record_count": record_count,
        "files": file_hashes,
        "fingerprint_scheme": "hmac-sha256-v1",
    }
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = sign_ed25519(issuer.private, payload)
    doc = {
        "manifest": manifest,
        "issuer_public": issuer.export_public_hex(),
        "sig": sig.hex(),
    }
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    # detached sig file
    path.with_suffix(".sig").write_text(
        json.dumps({"alg": "ed25519", "sig": sig.hex()}, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest, sig


def package_standard_dataset(
    *,
    records: list[dict[str, Any]],
    out_dir: Path,
    ctx: FingerprintContext,
    issuer: IssuerKeys,
    ledger: DeliveryLedger | None = None,
    customer_email: str | None = None,
    notes: str | None = None,
    packaged_on: date | None = None,
) -> dict[str, Any]:
    """Build Standard Dataset package. Facts unchanged; only surrogate IDs + order."""
    out_dir.mkdir(parents=True, exist_ok=True)
    packaged_on = packaged_on or date.today()
    id_map = build_export_id_map(records, ctx)
    ordered = permute_rows(records, ctx)
    rows = attach_export_ids(ordered, id_map)
    banner = visible_licence_banner(ctx)

    # Placeholder delivery id until ledger assigns one; regenerate provenance after.
    provisional_delivery = "pending"
    provenance = provenance_payload(ctx, provisional_delivery)

    csv_path = out_dir / "faculty_catalog.csv"
    json_path = out_dir / "faculty_catalog.json"
    xlsx_path = out_dir / "faculty_catalog.xlsx"
    sqlite_path = out_dir / "faculty_catalog.sqlite"
    write_csv(csv_path, rows, banner)
    write_json(json_path, rows, provenance)
    write_xlsx(xlsx_path, rows, banner, provenance, packaged_on=packaged_on)
    write_sqlite(sqlite_path, rows, provenance)

    file_hashes = {
        csv_path.name: sha256_file(csv_path),
        json_path.name: sha256_file(json_path),
        xlsx_path.name: sha256_file(xlsx_path),
        sqlite_path.name: sha256_file(sqlite_path),
    }

    delivery_id = "local"
    if ledger is not None:
        # Sample first N export IDs for later leak lookup
        sample = {cid: eid for i, (cid, eid) in enumerate(id_map.items()) if i < 64}
        rec = ledger.record_delivery(
            license_id=ctx.license_id,
            customer_id=ctx.customer_id,
            customer_email=customer_email,
            sku=SKU.STANDARD_DATASET.value,
            fingerprint_salt=ctx.fingerprint_salt,
            file_hashes=file_hashes,
            export_id_samples=sample,
            notes=notes,
        )
        delivery_id = rec.delivery_id
        provenance = provenance_payload(ctx, delivery_id)
        # Rewrite JSON/XLSX/SQLite provenance with real delivery_id
        write_json(json_path, rows, provenance)
        write_xlsx(xlsx_path, rows, banner, provenance, packaged_on=packaged_on)
        write_sqlite(sqlite_path, rows, provenance)
        file_hashes = {
            csv_path.name: sha256_file(csv_path),
            json_path.name: sha256_file(json_path),
            xlsx_path.name: sha256_file(xlsx_path),
            sqlite_path.name: sha256_file(sqlite_path),
        }

    docs = write_customer_docs(
        out_dir,
        ctx=ctx,
        customer_email=customer_email,
        record_count=len(rows),
        banner=banner,
    )
    readme = out_dir / "README.txt"
    readme.write_text(
        banner
        + "\n\nYou received the complete faculty catalog for offline use.\n"
        "Start with START_HERE.txt. Factual fields match other legitimate deliveries; "
        "export_id values are unique to your licence for redistribution deterrence.\n",
        encoding="utf-8",
    )
    for name in [*docs, readme.name]:
        path = out_dir / name
        if path.exists() and path.is_file():
            file_hashes[name] = sha256_file(path)

    # Re-copy Excel alias after final xlsx hash inputs are stable
    alias = out_dir / "GlobalResearch.xlsx"
    alias.write_bytes(xlsx_path.read_bytes())
    file_hashes[alias.name] = sha256_file(alias)

    manifest_path = out_dir / "manifest.json"
    manifest, _sig = write_manifest(
        manifest_path,
        ctx=ctx,
        delivery_id=delivery_id,
        file_hashes=file_hashes,
        record_count=len(rows),
        issuer=issuer,
    )

    return {
        "out_dir": str(out_dir),
        "delivery_id": delivery_id,
        "record_count": len(rows),
        "file_hashes": file_hashes,
        "manifest_sha256": sha256_bytes(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ),
        "export_id_sample": {k: id_map[k] for k in list(id_map)[:5]},
    }
