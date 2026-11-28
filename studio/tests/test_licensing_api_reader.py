"""Licensing API, Reader UI, .aspkg wrap, monitor, unauthorized transfer."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("STUDIO_FORCE_LOCAL_SECRETS", "1")

from studio.app import create_app
from studio.dataset.asdb import open_asdb
from studio.dataset.fingerprint import FingerprintContext
from studio.dataset.package_cipher import build_aspkg, extract_aspkg
from studio.dataset.package_protected import build_protected_package
from studio.dataset.records import records_from_sqlite
from studio.db import connect, migrate
from studio.licensing.activation import LicenseStore, build_activation_request
from studio.licensing.crypto import IssuerKeys, b64e
from studio.licensing.device import create_device_identity
from studio.licensing.ledger import DeliveryLedger
from studio.licensing.monitor import evaluate_public_text, scan_local_corpus
from studio.licensing.products import SKU
from studio.summer_loader import seed_mini_bundled


@pytest.fixture()
def studio_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("STUDIO_DATA_DIR", str(home))
    monkeypatch.setenv("STUDIO_FORCE_LOCAL_SECRETS", "1")
    monkeypatch.setenv("STUDIO_LICENSING_WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.delenv("STUDIO_PROTECTED_PACKAGE", raising=False)
    return home


@pytest.fixture()
def client(studio_home):
    app = create_app(data_dir=studio_home)
    return TestClient(app, base_url="http://127.0.0.1:8765")


@pytest.fixture()
def mini_records(studio_home):
    conn = connect()
    migrate(conn)
    seed_mini_bundled(conn)
    rows = records_from_sqlite(conn)
    conn.close()
    return rows


def test_editions_api(client):
    r = client.get("/api/licensing/editions")
    assert r.status_code == 200
    body = r.json()
    assert "standard_dataset" in body["editions"]
    assert "academic_studio" in body["editions"]
    assert "protected_dataset" not in body["editions"]  # internal packaging alias
    assert body["editions"]["academic_studio"]["device_bound"] is True
    assert body["editions"]["academic_studio"]["licence_included"] is True
    assert body["editions"]["standard_dataset"]["list_price_usd"] == 14.99
    assert body["editions"]["academic_studio"]["list_price_usd"] == 39.99
    assert len(body["editions"]) == 2


def test_payment_webhook_and_activate_local(client, studio_home):
    bad = client.post(
        "/api/licensing/webhook/payment",
        json={
            "customer_id": "c1",
            "customer_email": "c1@example.com",
            "sku": "protected_dataset",
        },
        headers={"X-Studio-Webhook-Secret": "wrong"},
    )
    assert bad.status_code == 401

    ok = client.post(
        "/api/licensing/webhook/payment",
        json={
            "customer_id": "c1",
            "customer_email": "c1@example.com",
            "sku": "protected_dataset",
            "external_payment_id": "pay_123",
        },
        headers={"X-Studio-Webhook-Secret": "test-webhook-secret"},
    )
    assert ok.status_code == 200
    license_id = ok.json()["license_id"]
    assert "dek" not in ok.json()

    act = client.post(
        "/api/licensing/activate-local",
        json={"license_id": license_id},
    )
    assert act.status_code == 200
    assert Path(act.json()["aslic_path"]).exists()

    st = client.get(f"/api/licensing/status/{license_id}")
    assert st.status_code == 200
    assert st.json()["device_count"] == 1


def test_activate_challenge_endpoint(client, studio_home):
    client.post(
        "/api/licensing/webhook/payment",
        json={
            "customer_id": "c2",
            "customer_email": "c2@example.com",
            "sku": "academic_studio",
        },
        headers={"X-Studio-Webhook-Secret": "test-webhook-secret"},
    )
    # pull license id from store
    from studio.licensing.service import license_store

    store = license_store()
    license_id = next(iter(json.loads((studio_home / "license_store.json").read_text())["purchases"]))
    device = create_device_identity()
    req = build_activation_request(device, license_id)
    payload = {
        **{k: v for k, v in req.to_dict().items()},
    }
    r = client.post("/api/licensing/activate", json=payload)
    assert r.status_code == 200
    assert "-----" not in r.json()["aslic"]  # JSON aslic
    assert "wrapped_dek" in r.json()["aslic"]


def test_reader_ui_with_package(client, studio_home, mini_records, tmp_path, monkeypatch):
    issuer = IssuerKeys.generate()
    # Force service issuer to match package
    (studio_home / "dev_issuer.json").write_text(
        json.dumps(
            {"private_hex": issuer.export_private_hex(), "public_hex": issuer.export_public_hex()}
        ),
        encoding="utf-8",
    )
    store = LicenseStore(studio_home / "license_store.json", issuer)
    purchase = store.register_purchase(
        customer_id="reader_c",
        customer_email="r@example.com",
        sku=SKU.PROTECTED_DATASET,
    )
    device = create_device_identity()
    # Persist device into secrets so reader uses same identity
    from studio.licensing.device import DEVICE_SECRET_NAME
    from studio.secrets_store import set_secret

    set_secret(DEVICE_SECRET_NAME, device.to_storage())

    out = tmp_path / "pkg"
    build_protected_package(
        records=mini_records,
        out_dir=out,
        ctx=FingerprintContext("reader_c", purchase.fingerprint_salt, purchase.license_id),
        issuer=issuer,
        dek=purchase.dek,
        sku=SKU.PROTECTED_DATASET,
        activate_for_device=device,
        license_store=store,
        license_id=purchase.license_id,
    )
    monkeypatch.setenv("STUDIO_PROTECTED_PACKAGE", str(out))
    r = client.get("/reader")
    assert r.status_code == 200
    assert "Academic Data Reader" in r.text
    assert "Ada Example" in r.text
    export = client.get("/reader/export.csv?limit=10")
    assert export.status_code == 200
    assert b"export_id" in export.content
    assert b"Ada Example" in export.content


def test_aspkg_roundtrip_and_wrong_key(mini_records, tmp_path, studio_home):
    issuer = IssuerKeys.generate()
    store = LicenseStore(studio_home / "license_store.json", issuer)
    purchase = store.register_purchase(
        customer_id="pkg", customer_email="p@x.com", sku=SKU.PROTECTED_DATASET
    )
    out = tmp_path / "p"
    build_protected_package(
        records=mini_records,
        out_dir=out,
        ctx=FingerprintContext("pkg", purchase.fingerprint_salt, purchase.license_id),
        issuer=issuer,
        dek=purchase.dek,
        sku=SKU.PROTECTED_DATASET,
    )
    assert (out / "ResearchCatalog.aspkg").exists()
    dest = tmp_path / "extracted"
    members = extract_aspkg(out / "ResearchCatalog.aspkg", dest, purchase.dek)
    assert "ResearchCatalog.asdb" in members
    conn = open_asdb(dest / "ResearchCatalog.asdb", purchase.dek)
    assert conn.execute("SELECT COUNT(*) FROM faculty").fetchone()[0] == len(mini_records)
    conn.close()
    with pytest.raises(Exception):
        extract_aspkg(out / "ResearchCatalog.aspkg", tmp_path / "bad", b"\x01" * 32)


def test_forwarded_package_without_aslic_unusable(mini_records, tmp_path, studio_home):
    issuer = IssuerKeys.generate()
    store = LicenseStore(studio_home / "license_store.json", issuer)
    purchase = store.register_purchase(
        customer_id="fwd", customer_email="f@x.com", sku=SKU.PROTECTED_DATASET
    )
    device = create_device_identity()
    out = tmp_path / "orig"
    build_protected_package(
        records=mini_records,
        out_dir=out,
        ctx=FingerprintContext("fwd", purchase.fingerprint_salt, purchase.license_id),
        issuer=issuer,
        dek=purchase.dek,
        activate_for_device=device,
        license_store=store,
        license_id=purchase.license_id,
    )
    # Simulate forwarding only the encrypted DB
    stolen = tmp_path / "stolen"
    stolen.mkdir()
    (stolen / "ResearchCatalog.asdb").write_bytes((out / "ResearchCatalog.asdb").read_bytes())
    with pytest.raises(Exception):
        open_asdb(stolen / "ResearchCatalog.asdb", b"\x00" * 32)
    # Without aslic, reader activation fails
    from studio.dataset.reader import activate_local_catalog

    with pytest.raises(FileNotFoundError):
        activate_local_catalog(stolen, issuer_public_hex=issuer.export_public_hex(), device=device)


def test_monitor_matches_export_ids(studio_home, mini_records, tmp_path):
    issuer = IssuerKeys.generate()
    store = LicenseStore(studio_home / "license_store.json", issuer)
    purchase = store.register_purchase(
        customer_id="mon", customer_email="m@x.com", sku=SKU.STANDARD_DATASET
    )
    from studio.dataset.package_standard import package_standard_dataset

    ledger = DeliveryLedger(studio_home / "delivery_ledger.sqlite")
    out = tmp_path / "std"
    result = package_standard_dataset(
        records=mini_records,
        out_dir=out,
        ctx=FingerprintContext("mon", purchase.fingerprint_salt, purchase.license_id),
        issuer=issuer,
        ledger=ledger,
    )
    sample_eid = next(iter(result["export_id_sample"].values()))
    leak = tmp_path / "forum_post.txt"
    leak.write_text(
        f"Selling Academic Outreach Studio dump with {sample_eid} and ResearchCatalog.asdb",
        encoding="utf-8",
    )
    findings = scan_local_corpus([leak], ledger)
    assert findings
    assert any(sample_eid in f.export_ids for f in findings)
    assert any(f.ledger_hits for f in findings)
    # Explicit non-accusation note
    assert "Candidate only" in findings[0].notes


def test_revoke_blocks_later_activation(client):
    r = client.post(
        "/api/licensing/webhook/payment",
        json={
            "customer_id": "rev",
            "customer_email": "rev@example.com",
            "sku": "protected_dataset",
        },
        headers={"X-Studio-Webhook-Secret": "test-webhook-secret"},
    )
    license_id = r.json()["license_id"]
    rev = client.post(
        f"/api/licensing/revoke/{license_id}",
        headers={"X-Studio-Webhook-Secret": "test-webhook-secret"},
    )
    assert rev.status_code == 200
    act = client.post("/api/licensing/activate-local", json={"license_id": license_id})
    assert act.status_code == 403
