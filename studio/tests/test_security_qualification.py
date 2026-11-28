"""Security qualification additions — device backends, forensic inspector, policies."""

from __future__ import annotations

import json

import pytest

from studio.dataset.fingerprint import FingerprintContext, export_id_for, provenance_payload
from studio.dataset.forensic import inspect_path
from studio.licensing.device_backend import (
    BindingMode,
    HardwareBackendStub,
    SoftwareFileBackend,
    describe_device_security,
    select_device_backend,
)
from studio.licensing.ledger import DeliveryLedger
from studio.licensing.policy import DATASET_POLICY, STUDIO_POLICY, policies


@pytest.fixture()
def studio_home(tmp_path, monkeypatch):
    home = tmp_path / "sec-home"
    monkeypatch.setenv("STUDIO_DATA_DIR", str(home))
    monkeypatch.setenv("STUDIO_FORCE_LOCAL_SECRETS", "1")
    return home


def test_device_backend_software_fallback(monkeypatch):
    monkeypatch.setenv("STUDIO_FORCE_LOCAL_SECRETS", "1")
    monkeypatch.delenv("STUDIO_DEVICE_BACKEND", raising=False)
    backend = select_device_backend()
    assert isinstance(backend, SoftwareFileBackend)
    caps = backend.capabilities()
    assert caps.binding == BindingMode.SOFTWARE
    assert caps.exportable_private_keys is True


def test_hardware_backend_stub_not_silently_selected(monkeypatch):
    monkeypatch.setenv("STUDIO_FORCE_LOCAL_SECRETS", "1")
    monkeypatch.delenv("STUDIO_DEVICE_BACKEND", raising=False)
    backend = select_device_backend()
    assert not isinstance(backend, HardwareBackendStub)
    summary = describe_device_security()
    assert summary["hardware_adapter"]["status"] == "not_implemented"
    assert "software identity" in summary["honest_claim"].lower()


def test_device_api_reports_binding(client):
    r = client.get("/api/licensing/device")
    assert r.status_code == 200
    body = r.json()
    assert body["binding"] in {"software", "keyring", "hardware"}
    assert "exportable_private_keys" in body
    assert body["security_summary"]["hardware_adapter"]["status"] == "not_implemented"


def test_editions_include_licence_policies(client):
    r = client.get("/api/licensing/editions")
    body = r.json()
    assert "licence_policies" in body
    assert body["licence_policies"]["standard_dataset"]["licence_included_in_price"] is True
    assert body["licence_policies"]["academic_studio"]["authorized_devices"] == "2"
    assert "third_party_ai" in body["licence_policies"]["academic_studio"]


def test_policies_perpetual_not_unlimited_updates():
    assert DATASET_POLICY.usage_duration.startswith("perpetual")
    assert "not unlimited" in DATASET_POLICY.updates_included.lower() or "not" in DATASET_POLICY.updates_included.lower()
    assert STUDIO_POLICY.additional_activation_charge is False
    assert STUDIO_POLICY.device_bound_activation is True
    assert "API credits" in STUDIO_POLICY.third_party_ai or "credits" in STUDIO_POLICY.third_party_ai.lower()
    assert set(policies()) == {"standard_dataset", "academic_studio"}


def test_forensic_inspector_no_auto_accusation(tmp_path, studio_home):
    ctx_a = FingerprintContext(customer_id="cust_a", fingerprint_salt="salt_a", license_id="lic_a")
    ctx_b = FingerprintContext(customer_id="cust_b", fingerprint_salt="salt_b", license_id="lic_b")
    id_a = export_id_for(ctx_a, "canonical-1")
    id_b = export_id_for(ctx_b, "canonical-1")
    assert id_a != id_b

    folder = tmp_path / "leak"
    folder.mkdir()
    (folder / "faculty_catalog.csv").write_text(
        f"export_id,name\n{id_a},Ada Example\n{id_a},Kept Fact\n{id_a},Third\n",
        encoding="utf-8",
    )
    (folder / "manifest.json").write_text(
        json.dumps(provenance_payload(ctx_a, delivery_id="del_a")),
        encoding="utf-8",
    )

    ledger = DeliveryLedger(studio_home / "delivery_ledger.sqlite")
    ledger.record_delivery(
        license_id="lic_a",
        customer_id="cust_a",
        sku="standard_dataset",
        fingerprint_salt="salt_a",
        file_hashes={"faculty_catalog.csv": "abc"},
        export_id_samples={"canonical-1": id_a, "canonical-2": id_a, "canonical-3": id_a},
        customer_email="a@example.com",
        package_sha256="deadbeef",
    )

    report = inspect_path(folder, ledger)
    assert id_a in report.surviving_fingerprints
    assert report.attribution_confidence in {"medium", "high"}
    assert any("accuse" in n.lower() for n in report.notes)
    assert report.limitations


def test_forensic_cli(studio_home, tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_FORCE_LOCAL_SECRETS", "1")
    leak = tmp_path / "sample.csv"
    leak.write_text("export_id\nR-ABCDEF12\n", encoding="utf-8")
    from studio.dataset.cli import main

    rc = main(["forensic", "--path", str(leak)])
    assert rc == 0


def test_reader_integrated_copy(client):
    r = client.get("/reader")
    assert r.status_code == 200
    assert "Integrated Catalog Reader" in r.text or "Catalog Reader" in r.text
    d = client.get("/directory")
    assert "/reader" in d.text
