"""Issuer vault, payment idempotency, update manifests, activation replay."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from studio.licensing.activation import (
    ActivationRequest,
    LicenseStore,
    activate_device,
    build_activation_request,
)
from studio.licensing.crypto import IssuerKeys, b64e
from studio.licensing.device import create_device_identity
from studio.licensing.issuer_vault import load_vault, write_vault
from studio.licensing.payments import append_payment_event, iter_payment_events
from studio.licensing.updates import (
    build_update_manifest,
    verify_payload_file,
    verify_update_manifest,
    write_signed_update_manifest,
)


@pytest.fixture()
def studio_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("STUDIO_DATA_DIR", str(home))
    monkeypatch.setenv("STUDIO_FORCE_LOCAL_SECRETS", "1")
    return home


def test_issuer_vault_roundtrip(tmp_path):
    keys = IssuerKeys.generate()
    path = tmp_path / "vault.json"
    write_vault(keys, "correct-horse-battery-staple", path)
    loaded = load_vault("correct-horse-battery-staple", path)
    assert loaded.export_public_hex() == keys.export_public_hex()
    with pytest.raises(Exception):
        load_vault("wrong-passphrase-xx", path)


def test_production_mode_refuses_dev_autogen(studio_home, monkeypatch):
    monkeypatch.setenv("STUDIO_ISSUER_MODE", "production")
    monkeypatch.delenv("STUDIO_ISSUER_PRIVATE_HEX", raising=False)
    monkeypatch.delenv("STUDIO_ISSUER_VAULT_PASSPHRASE", raising=False)
    from studio.licensing.service import issuer_keys

    with pytest.raises(RuntimeError, match="production"):
        issuer_keys()


def test_payment_idempotency_by_external_id(studio_home):
    issuer = IssuerKeys.generate()
    store = LicenseStore(studio_home / "license_store.json", issuer)
    a = store.register_purchase(
        customer_id="c1",
        customer_email="a@example.com",
        sku="academic_studio",
        external_payment_id="pay_123",
        payment_provider="fastspring",
    )
    b = store.register_purchase(
        customer_id="c1",
        customer_email="a@example.com",
        sku="academic_studio",
        external_payment_id="pay_123",
        payment_provider="fastspring",
    )
    assert a.license_id == b.license_id
    with pytest.raises(ValueError, match="already bound"):
        store.register_purchase(
            customer_id="c1",
            customer_email="a@example.com",
            sku="standard_dataset",
            external_payment_id="pay_123",
        )


def test_payment_event_log(studio_home):
    path = studio_home / "payment_events.jsonl"
    append_payment_event({"event": "purchase_registered", "license_id": "lic_x"}, path=path)
    rows = iter_payment_events(path)
    assert len(rows) == 1
    assert rows[0]["event"] == "purchase_registered"


def test_signed_update_manifest(tmp_path, studio_home):
    issuer = IssuerKeys.generate()
    payload = tmp_path / "AcademicStudio.zip"
    payload.write_bytes(b"fake-installer-bytes")
    manifest = build_update_manifest(
        version="1.0.0",
        channel="stable",
        payload_path=payload,
        payload_url="https://example.invalid/AcademicStudio.zip",
    )
    out = tmp_path / "updates"
    man_path, sig_path = write_signed_update_manifest(out, manifest, issuer)
    man = json.loads(man_path.read_text(encoding="utf-8"))
    sig = sig_path.read_text(encoding="utf-8").strip()
    assert verify_update_manifest(man, sig, issuer.export_public_hex())
    assert verify_payload_file(man, payload)
    assert not verify_update_manifest(man, sig, IssuerKeys.generate().export_public_hex())


def test_activation_nonce_replay_rejected(studio_home):
    issuer = IssuerKeys.generate()
    store = LicenseStore(studio_home / "license_store.json", issuer)
    rec = store.register_purchase(
        customer_id="c1",
        customer_email="a@example.com",
        sku="academic_studio",
    )
    device = create_device_identity()
    req = build_activation_request(device, rec.license_id)
    out1 = studio_home / "a1.aslic"
    activate_device(store, req, aslic_path=out1)
    with pytest.raises(PermissionError, match="nonce"):
        activate_device(store, req, aslic_path=studio_home / "a2.aslic")


def test_hardware_probe_honest(studio_home):
    from studio.licensing.device_backend import describe_device_security, probe_hardware_presence

    probe = probe_hardware_presence()
    assert "platform" in probe
    summary = describe_device_security()
    assert summary["hardware_adapter"]["status"] == "not_implemented"
    assert "software identity" in summary["honest_claim"]
