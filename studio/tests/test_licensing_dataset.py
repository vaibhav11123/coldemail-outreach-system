"""Licensing + fingerprinted/encrypted dataset packaging."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ["STUDIO_FORCE_LOCAL_SECRETS"] = "1"

from studio.dataset.asdb import open_asdb
from studio.dataset.fingerprint import FingerprintContext, export_id_for
from studio.dataset.package_protected import build_protected_package
from studio.dataset.package_standard import package_standard_dataset
from studio.dataset.reader import activate_local_catalog
from studio.dataset.records import records_from_sqlite
from studio.db import connect, migrate
from studio.licensing.activation import (
    LicenseStore,
    activate_device,
    build_activation_request,
)
from studio.licensing.crypto import IssuerKeys
from studio.licensing.device import create_device_identity, load_or_create_device_identity
from studio.licensing.entitlement import read_aslic
from studio.licensing.ledger import DeliveryLedger
from studio.licensing.products import SKU, get_edition
from studio.packaging_scan import scan_package_dir
from studio.summer_loader import seed_mini_bundled


@pytest.fixture()
def studio_home(tmp_path, monkeypatch):
    home = tmp_path / "studio-home"
    monkeypatch.setenv("STUDIO_DATA_DIR", str(home))
    monkeypatch.setenv("STUDIO_FORCE_LOCAL_SECRETS", "1")
    return home


@pytest.fixture()
def mini_records(studio_home):
    conn = connect()
    migrate(conn)
    seed_mini_bundled(conn)
    rows = records_from_sqlite(conn)
    conn.close()
    assert len(rows) >= 2
    return rows


def test_editions_preserve_full_catalog_access():
    for sku in SKU:
        ed = get_edition(sku)
        assert ed.includes_full_catalog is True
    assert get_edition(SKU.STANDARD_DATASET).machine_readable_exports is True
    assert get_edition(SKU.PROTECTED_DATASET).device_bound is True
    assert get_edition(SKU.ACADEMIC_STUDIO).includes_studio_features is True


def test_export_ids_differ_across_customers_facts_unchanged(mini_records):
    a = FingerprintContext("cust_a", "salt_a", "lic_a")
    b = FingerprintContext("cust_b", "salt_b", "lic_b")
    cid = mini_records[0]["canonical_id"]
    assert export_id_for(a, cid) != export_id_for(b, cid)
    # Facts themselves are not rewritten by fingerprint helpers
    assert mini_records[0]["display_name"]
    assert "@" in (mini_records[0]["email"] or "")


def test_standard_package_fingerprints_and_ledger(studio_home, mini_records, tmp_path):
    issuer = IssuerKeys.generate()
    store = LicenseStore(studio_home / "license_store.json", issuer)
    purchase = store.register_purchase(
        customer_id="cust_std",
        customer_email="std@example.com",
        sku=SKU.STANDARD_DATASET,
    )
    ctx = FingerprintContext(
        customer_id="cust_std",
        fingerprint_salt=purchase.fingerprint_salt,
        license_id=purchase.license_id,
    )
    ledger = DeliveryLedger(studio_home / "delivery_ledger.sqlite")
    out = tmp_path / "standard"
    result = package_standard_dataset(
        records=mini_records,
        out_dir=out,
        ctx=ctx,
        issuer=issuer,
        ledger=ledger,
        customer_email="std@example.com",
    )
    assert (out / "faculty_catalog.csv").exists()
    assert (out / "faculty_catalog.xlsx").exists()
    assert (out / "manifest.json").exists()
    assert (out / "manifest.sig").exists()
    csv_text = (out / "faculty_catalog.csv").read_text(encoding="utf-8")
    assert "Licensed to customer cust_std" in csv_text
    assert "Ada Example" in csv_text
    sample_eid = next(iter(result["export_id_sample"].values()))
    hits = ledger.find_by_export_ids([sample_eid])
    assert hits
    assert hits[0]["customer_id"] == "cust_std"
    scan_package_dir(out)


def test_two_customers_standard_packages_have_different_ids(studio_home, mini_records, tmp_path):
    issuer = IssuerKeys.generate()
    ledger = DeliveryLedger(studio_home / "delivery_ledger.sqlite")
    outs = []
    for cust in ("alice", "bob"):
        store = LicenseStore(studio_home / f"store_{cust}.json", issuer)
        purchase = store.register_purchase(
            customer_id=cust, customer_email=f"{cust}@ex.com", sku=SKU.STANDARD_DATASET
        )
        ctx = FingerprintContext(cust, purchase.fingerprint_salt, purchase.license_id)
        out = tmp_path / cust
        package_standard_dataset(
            records=mini_records, out_dir=out, ctx=ctx, issuer=issuer, ledger=ledger
        )
        outs.append((out / "faculty_catalog.json").read_text(encoding="utf-8"))
    ja, jb = (json.loads(x) for x in outs)
    ids_a = {r["export_id"] for r in ja["records"]}
    ids_b = {r["export_id"] for r in jb["records"]}
    assert ids_a.isdisjoint(ids_b)
    names_a = {r["display_name"] for r in ja["records"]}
    names_b = {r["display_name"] for r in jb["records"]}
    assert names_a == names_b


def test_protected_package_device_bound(studio_home, mini_records, tmp_path):
    issuer = IssuerKeys.generate()
    store = LicenseStore(studio_home / "license_store.json", issuer)
    purchase = store.register_purchase(
        customer_id="cust_p",
        customer_email="p@example.com",
        sku=SKU.PROTECTED_DATASET,
    )
    ctx = FingerprintContext("cust_p", purchase.fingerprint_salt, purchase.license_id)
    device_a = create_device_identity()
    out = tmp_path / "protected"
    result = build_protected_package(
        records=mini_records,
        out_dir=out,
        ctx=ctx,
        issuer=issuer,
        dek=purchase.dek,
        sku=SKU.PROTECTED_DATASET,
        ledger=DeliveryLedger(studio_home / "delivery_ledger.sqlite"),
        activate_for_device=device_a,
        license_store=store,
        license_id=purchase.license_id,
    )
    assert result["activated"] is True
    assert (out / "ResearchCatalog.asdb").exists()
    assert (out / "CustomerLicense.aslic").exists()

    # Authorized device unlocks
    session = activate_local_catalog(
        out,
        issuer_public_hex=issuer.export_public_hex(),
        device=device_a,
    )
    hits = session.search(query="Ada")
    assert hits and hits[0]["display_name"] == "Ada Example"
    assert session.record_count() == len(mini_records)

    # Wrong key cannot open catalog
    with pytest.raises(Exception):
        open_asdb(out / "ResearchCatalog.asdb", b"\x00" * 32)

    # Another device cannot unwrap the sealed DEK
    device_b = create_device_identity()
    ent = read_aslic(out / "CustomerLicense.aslic", expected_issuer_public=issuer.public)
    with pytest.raises(PermissionError):
        ent.unwrap_dek(device_b)


def test_device_limit_two_and_replacement(studio_home, mini_records, tmp_path):
    issuer = IssuerKeys.generate()
    store = LicenseStore(studio_home / "license_store.json", issuer)
    purchase = store.register_purchase(
        customer_id="cust_lim",
        customer_email="lim@example.com",
        sku=SKU.PROTECTED_DATASET,
    )
    d1, d2, d3 = create_device_identity(), create_device_identity(), create_device_identity()
    for d in (d1, d2):
        req = build_activation_request(d, purchase.license_id)
        activate_device(store, req, aslic_path=tmp_path / f"{d.device_id}.aslic")
    req3 = build_activation_request(d3, purchase.license_id)
    with pytest.raises(PermissionError, match="Device limit"):
        activate_device(store, req3, aslic_path=tmp_path / "d3.aslic")
    # Replace d1 with d3
    activate_device(
        store,
        req3,
        aslic_path=tmp_path / "d3.aslic",
        replace_device_id=d1.device_id,
    )
    rec = store.get(purchase.license_id)
    assert d1.device_id not in rec.activated_devices
    assert d3.device_id in rec.activated_devices


def test_revocation_blocks_activation(studio_home, tmp_path):
    issuer = IssuerKeys.generate()
    store = LicenseStore(studio_home / "license_store.json", issuer)
    purchase = store.register_purchase(
        customer_id="cust_r",
        customer_email="r@example.com",
        sku=SKU.ACADEMIC_STUDIO,
    )
    store.revoke(purchase.license_id)
    device = create_device_identity()
    req = build_activation_request(device, purchase.license_id)
    with pytest.raises(PermissionError, match="revoked"):
        activate_device(store, req, aslic_path=tmp_path / "x.aslic")


def test_packaging_scan_rejects_issuer_secret(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "ok.txt").write_text("hello", encoding="utf-8")
    scan_package_dir(pkg)
    (pkg / "leak.txt").write_text("STUDIO_ISSUER_PRIVATE_HEX=abc", encoding="utf-8")
    with pytest.raises(SystemExit):
        scan_package_dir(pkg)


def test_load_or_create_device_stable(studio_home):
    a = load_or_create_device_identity()
    b = load_or_create_device_identity()
    assert a.device_id == b.device_id
    assert a.fingerprint == b.fingerprint


def test_cli_editions(studio_home):
    from studio.dataset.cli import main

    assert main(["editions"]) == 0


def test_cli_fulfil_requires_verified_payment(studio_home, tmp_path):
    from studio.dataset.cli import main

    rc = main(
        [
            "fulfil",
            "--sku",
            "dataset",
            "--out",
            str(tmp_path / "nope"),
            "--customer",
            "c",
            "--email",
            "c@e.edu",
            "--provider",
            "paypal",
            "--payment-ref",
            "X",
        ]
    )
    assert rc == 2


def test_cli_fulfil_dataset_writes_receipt(studio_home, tmp_path):
    from studio.dataset.cli import main

    out = tmp_path / "fulfil_dataset"
    rc = main(
        [
            "fulfil",
            "--sku",
            "dataset",
            "--out",
            str(out),
            "--customer",
            "cust_fulfil",
            "--email",
            "fulfil@example.edu",
            "--provider",
            "paypal",
            "--payment-ref",
            "TXN-TEST-001",
            "--verified-by",
            "pytest",
            "--verified-payment",
        ]
    )
    assert rc == 0
    receipt = json.loads((out / "fulfilment_receipt.json").read_text(encoding="utf-8"))
    assert receipt["mode"] == "manual_fulfilment"
    assert receipt["sku"] == SKU.STANDARD_DATASET.value
    assert receipt["payment_provider"] == "paypal"
    assert receipt["external_payment_id"] == "TXN-TEST-001"
    assert receipt["payment_verified"] is True
    assert (out / "faculty_catalog.csv").exists()
    assert (out / "faculty_catalog.sqlite").exists()
    assert (out / "START_HERE.txt").exists()
    assert (out / "GlobalResearch.xlsx").exists()
    assert (out / "DELIVERY_INSTRUCTIONS.txt").exists()
    assert (out / "manifest.json").exists()
    store_raw = json.loads((studio_home / "license_store.json").read_text(encoding="utf-8"))
    purchase = next(iter(store_raw["purchases"].values()))
    assert purchase["external_payment_id"] == "TXN-TEST-001"
    assert purchase["payment_provider"] == "paypal"


def test_cli_issue_licence_from_activation_request(studio_home, tmp_path):
    from studio.dataset.cli import main
    from studio.licensing.activation import LicenseStore, build_activation_request
    from studio.licensing.crypto import IssuerKeys
    from studio.licensing.device import create_device_identity

    issuer = IssuerKeys.generate()
    studio_home.mkdir(parents=True, exist_ok=True)
    # Persist issuer the CLI will load
    (studio_home / "dev_issuer.json").write_text(
        json.dumps(
            {
                "private_hex": issuer.export_private_hex(),
                "public_hex": issuer.export_public_hex(),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    store = LicenseStore(studio_home / "license_store.json", issuer)
    purchase = store.register_purchase(
        customer_id="cust_act",
        customer_email="act@example.edu",
        sku=SKU.ACADEMIC_STUDIO,
        payment_provider="paypal",
        external_payment_id="TXN-ACT",
    )
    device = create_device_identity()
    req = build_activation_request(device, purchase.license_id)
    req_path = tmp_path / "activation_request.json"
    req_path.write_text(json.dumps(req.to_dict(), indent=2) + "\n", encoding="utf-8")
    aslic = tmp_path / "CustomerLicense.aslic"
    rc = main(
        [
            "issue-licence",
            "--request",
            str(req_path),
            "--out",
            str(aslic),
            "--license-id",
            purchase.license_id,
        ]
    )
    assert rc == 0
    assert aslic.exists()
    doc = json.loads(aslic.read_text(encoding="utf-8"))
    assert doc["format"] == "academic-studio-license"
    assert doc["entitlement"]["license_id"] == purchase.license_id
    assert doc["entitlement"]["device_id"] == device.device_id
