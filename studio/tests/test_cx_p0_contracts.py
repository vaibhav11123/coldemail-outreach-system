"""P0 CX contracts: mail simulation, packaging HR deny, package-issuer Reader trust."""

from __future__ import annotations

import json

import pytest

from studio.dataset.fingerprint import FingerprintContext
from studio.dataset.package_protected import build_protected_package
from studio.dataset.reader import activate_local_catalog
from studio.dataset.reader_routes import _package_issuer_public_hex
from studio.drafts import content_hash
from studio.licensing.activation import LicenseStore
from studio.licensing.crypto import IssuerKeys
from studio.licensing.device import create_device_identity
from studio.licensing.products import SKU
from studio.mailer_studio import create_intent, mail_transport_mode, perform_send
from studio.packaging_scan import scan_package_dir


def test_mail_mode_simulation_never_hits_smtp(conn, monkeypatch):
    monkeypatch.setenv("STUDIO_MAIL_MODE", "simulation")
    assert mail_transport_mode() == "simulation"
    rid = conn.execute(
        "INSERT INTO researcher(display_name, origin) VALUES ('T', 'test')"
    ).lastrowid
    oid = conn.execute(
        "INSERT INTO opportunity(researcher_id, kind, status) VALUES (?, 'internship', 'unknown')",
        (rid,),
    ).lastrowid
    body = "Dear Professor,\n\nHello.\n\nBest regards,\n"
    subject = "Hi"
    recipient = "t@example.com"
    h = content_hash(recipient, subject, body)
    did = conn.execute(
        """
        INSERT INTO draft(opportunity_id, recipient, subject, body, content_hash, approved_hash)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (oid, recipient, subject, body, h, h),
    ).lastrowid
    intent = create_intent(conn, did, h, provider="smtp")

    def boom(*_a, **_k):
        raise AssertionError("SMTP must not be called in simulation")

    monkeypatch.setattr("studio.mailer_studio.send_via_smtp", boom)
    assert perform_send(conn, intent, smtp_config={"host": "x", "port": 25}) == "simulated"


def test_packaging_scan_rejects_hr_csv(tmp_path):
    (tmp_path / "ok.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "cold_email_outreach_all_cleaned_ranked.csv").write_text(
        "a,b\n1,2\n", encoding="utf-8"
    )
    with pytest.raises(SystemExit):
        scan_package_dir(tmp_path)


def test_reader_trusts_package_issuer_not_operator(studio_home, mini_records, tmp_path, monkeypatch):
    """Package signed by key A opens even when local operator issuer is key B."""
    package_issuer = IssuerKeys.generate()
    operator = IssuerKeys.generate()
    assert package_issuer.export_public_hex() != operator.export_public_hex()

    store = LicenseStore(studio_home / "license_store.json", package_issuer)
    purchase = store.register_purchase(
        customer_id="cust_cx",
        customer_email="cx@example.com",
        sku=SKU.PROTECTED_DATASET,
    )
    ctx = FingerprintContext("cust_cx", purchase.fingerprint_salt, purchase.license_id)
    device = create_device_identity()
    out = tmp_path / "protected"
    build_protected_package(
        records=mini_records,
        out_dir=out,
        ctx=ctx,
        issuer=package_issuer,
        dek=purchase.dek,
        sku=SKU.PROTECTED_DATASET,
        activate_for_device=device,
        license_store=store,
        license_id=purchase.license_id,
    )

    # Poison local operator issuer so a naive issuer_keys() would mismatch
    (studio_home / "dev_issuer.json").write_text(
        json.dumps(
            {
                "private_hex": operator.export_private_hex(),
                "public_hex": operator.export_public_hex(),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("STUDIO_ISSUER_PRIVATE_HEX", raising=False)
    monkeypatch.delenv("STUDIO_TRUSTED_ISSUER_PUBLIC", raising=False)

    hex_key = _package_issuer_public_hex(out)
    assert hex_key == package_issuer.export_public_hex()
    session = activate_local_catalog(out, issuer_public_hex=hex_key, device=device)
    hits = session.search(query="Ada")
    assert hits
    assert session.record_count() == len(mini_records)

    # Operator key must still raise mismatch when forced
    with pytest.raises(PermissionError, match="issuer public key mismatch"):
        activate_local_catalog(
            out,
            issuer_public_hex=operator.export_public_hex(),
            device=device,
        )
