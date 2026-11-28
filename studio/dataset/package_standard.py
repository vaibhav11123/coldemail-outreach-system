"""Standard Dataset: personalized Excel, CSV, JSON with forensic fingerprints."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font

from studio.dataset.fingerprint import (
    FingerprintContext,
    export_id_for,
    permute_rows,
    provenance_payload,
    visible_licence_banner,
)
from studio.dataset.records import FACTUAL_FIELDS, attach_export_ids
from studio.licensing.crypto import IssuerKeys, sign_ed25519
from studio.licensing.ledger import DeliveryLedger, sha256_bytes, sha256_file
from studio.licensing.products import SKU


EXPORT_COLUMNS = ("export_id",) + FACTUAL_FIELDS


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


def write_xlsx(path: Path, rows: list[dict[str, Any]], banner: str, provenance: dict) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Faculty"
    ws["A1"] = banner
    ws["A1"].font = Font(bold=True, color="0B4F6C")
    headers = list(EXPORT_COLUMNS)
    for col, name in enumerate(headers, start=1):
        ws.cell(row=3, column=col, value=name)
    for i, row in enumerate(rows, start=4):
        for col, name in enumerate(headers, start=1):
            ws.cell(row=i, column=col, value=row.get(name))

    props = wb.properties
    props.creator = "Academic Outreach Studio"
    props.title = "Global Research Faculty Dataset (licensed delivery)"
    props.description = banner
    props.keywords = f"license:{provenance.get('license_id')};customer:{provenance.get('customer_id')}"

    prov = wb.create_sheet("Provenance")
    prov["A1"] = "Do not delete — delivery provenance"
    for i, (k, v) in enumerate(provenance.items(), start=3):
        prov.cell(row=i, column=1, value=k)
        prov.cell(row=i, column=2, value=str(v))
    # Hide provenance sheet (still present until inspected/removed)
    prov.sheet_state = "hidden"

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


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
) -> dict[str, Any]:
    """Build Standard Dataset package. Facts unchanged; only surrogate IDs + order."""
    out_dir.mkdir(parents=True, exist_ok=True)
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
    write_csv(csv_path, rows, banner)
    write_json(json_path, rows, provenance)
    write_xlsx(xlsx_path, rows, banner, provenance)

    file_hashes = {
        csv_path.name: sha256_file(csv_path),
        json_path.name: sha256_file(json_path),
        xlsx_path.name: sha256_file(xlsx_path),
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
        )
        delivery_id = rec.delivery_id
        provenance = provenance_payload(ctx, delivery_id)
        # Rewrite JSON/XLSX provenance with real delivery_id (CSV banner has licence ids)
        write_json(json_path, rows, provenance)
        write_xlsx(xlsx_path, rows, banner, provenance)
        file_hashes = {
            csv_path.name: sha256_file(csv_path),
            json_path.name: sha256_file(json_path),
            xlsx_path.name: sha256_file(xlsx_path),
        }

    manifest_path = out_dir / "manifest.json"
    manifest, _sig = write_manifest(
        manifest_path,
        ctx=ctx,
        delivery_id=delivery_id,
        file_hashes=file_hashes,
        record_count=len(rows),
        issuer=issuer,
    )
    readme = out_dir / "README.txt"
    readme.write_text(
        banner
        + "\n\nYou received the complete faculty catalog for offline use.\n"
        "Factual fields are identical to other legitimate deliveries; export_id "
        "values are unique to your licence for redistribution deterrence.\n",
        encoding="utf-8",
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
