"""Protected Dataset / Studio package layout with encrypted catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from studio.dataset.asdb import build_asdb
from studio.dataset.fingerprint import FingerprintContext, export_id_for
from studio.licensing.activation import LicenseStore, activate_device, build_activation_request
from studio.licensing.crypto import IssuerKeys, sign_ed25519
from studio.licensing.device import DeviceIdentity
from studio.licensing.ledger import DeliveryLedger, sha256_file
from studio.licensing.products import SKU, get_edition
from studio.packaging_scan import scan_package_dir


PACKAGE_DOC = """Academic Data Reader package
================================

Contents:
  ResearchCatalog.asdb   Encrypted faculty catalog (SQLCipher)
  CustomerLicense.aslic  Device-bound entitlement (after activation)
  manifest.json          Signed delivery manifest
  Documentation.txt      This file

Activation:
  1. Install Academic Data Reader / Academic Studio on your machine.
  2. Verify purchase (email / account).
  3. Activate — the licensing server seals the database key to this device.
  4. Work fully offline until the signed entitlement TTL requires revalidation.

Forwarding this folder to another machine will not unlock the catalog:
another device cannot unwrap the database key from your licence file.

Controlled exports remain customer-fingerprinted. Do not treat encryption as
absolute prevention of extraction after you have unlocked the catalog.
"""


def build_protected_package(
    *,
    records: list[dict[str, Any]],
    out_dir: Path,
    ctx: FingerprintContext,
    issuer: IssuerKeys,
    dek: bytes,
    sku: SKU | str = SKU.PROTECTED_DATASET,
    ledger: DeliveryLedger | None = None,
    customer_email: str | None = None,
    activate_for_device: DeviceIdentity | None = None,
    license_store: LicenseStore | None = None,
    license_id: str | None = None,
) -> dict[str, Any]:
    sku_value = sku.value if isinstance(sku, SKU) else str(sku)
    edition = get_edition(sku_value)
    if not edition.encrypted_catalog:
        raise ValueError(f"{sku_value} is not an encrypted-catalog SKU")

    out_dir.mkdir(parents=True, exist_ok=True)
    asdb_path = out_dir / "ResearchCatalog.asdb"
    build_asdb(asdb_path, records, dek=dek, ctx=ctx, sku=sku_value)

    doc_path = out_dir / "Documentation.txt"
    doc_path.write_text(PACKAGE_DOC, encoding="utf-8")

    id_map = {r["canonical_id"]: export_id_for(ctx, r["canonical_id"]) for r in records}
    file_hashes = {
        "ResearchCatalog.asdb": sha256_file(asdb_path),
        "Documentation.txt": sha256_file(doc_path),
    }

    delivery_id = "local"
    if ledger is not None:
        sample = {cid: eid for i, (cid, eid) in enumerate(id_map.items()) if i < 64}
        rec = ledger.record_delivery(
            license_id=ctx.license_id,
            customer_id=ctx.customer_id,
            customer_email=customer_email,
            sku=sku_value,
            fingerprint_salt=ctx.fingerprint_salt,
            file_hashes=file_hashes,
            export_id_samples=sample,
            package_sha256=file_hashes["ResearchCatalog.asdb"],
        )
        delivery_id = rec.delivery_id

    manifest = {
        "format": "academic-studio-delivery-manifest",
        "version": 1,
        "sku": sku_value,
        "customer_id": ctx.customer_id,
        "license_id": ctx.license_id,
        "delivery_id": delivery_id,
        "record_count": len(records),
        "files": file_hashes,
        "catalog": "ResearchCatalog.asdb",
        "encryption": "sqlcipher4",
        "fingerprint_scheme": "hmac-sha256-v1",
        "device_bound": True,
        "max_devices": edition.max_devices,
    }
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = sign_ed25519(issuer.private, payload)
    manifest_doc = {
        "manifest": manifest,
        "issuer_public": issuer.export_public_hex(),
        "sig": sig.hex(),
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_doc, indent=2) + "\n", encoding="utf-8")
    (out_dir / "manifest.sig").write_text(
        json.dumps({"alg": "ed25519", "sig": sig.hex()}, indent=2) + "\n",
        encoding="utf-8",
    )
    file_hashes["manifest.json"] = sha256_file(manifest_path)

    aslic_path = out_dir / "CustomerLicense.aslic"
    if activate_for_device is not None:
        if license_store is None or not license_id:
            raise ValueError("license_store and license_id required for local activation")
        req = build_activation_request(activate_for_device, license_id)
        activate_device(license_store, req, aslic_path=aslic_path)
        file_hashes["CustomerLicense.aslic"] = sha256_file(aslic_path)

    # Refuse shipping secrets / env files in the customer package
    scan_package_dir(out_dir)

    return {
        "out_dir": str(out_dir),
        "delivery_id": delivery_id,
        "record_count": len(records),
        "file_hashes": file_hashes,
        "asdb": str(asdb_path),
        "activated": aslic_path.exists(),
        "sku": sku_value,
    }
