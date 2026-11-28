"""CLI for packaging and activating dataset deliveries.

Examples:
  python -m studio.dataset fulfil --sku dataset --out /tmp/std --customer c1 --email a@b.c --provider paypal --payment-ref TXN1
  python -m studio.dataset package-standard --out /tmp/std --customer c1 --email a@b.c
  python -m studio.dataset package-protected --out /tmp/prot --customer c1 --activate
  python -m studio.dataset read --package /tmp/prot --query Ada
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from studio.dataset.fingerprint import FingerprintContext
from studio.dataset.package_protected import build_protected_package
from studio.dataset.package_standard import package_standard_dataset
from studio.dataset.reader import activate_local_catalog
from studio.dataset.records import records_from_sqlite
from studio.db import connect, migrate
from studio.licensing.activation import LicenseStore
from studio.licensing.crypto import IssuerKeys
from studio.licensing.device import load_or_create_device_identity
from studio.licensing.ledger import DeliveryLedger
from studio.licensing.products import SKU, editions
from studio.paths import app_data_dir
from studio.summer_loader import seed_mini_bundled


def _issuer_from_env() -> IssuerKeys:
    hex_key = os.environ.get("STUDIO_ISSUER_PRIVATE_HEX")
    if hex_key:
        return IssuerKeys.from_private_hex(hex_key)
    # Dev/demo issuer persisted under app data (NOT for production)
    path = app_data_dir() / "dev_issuer.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return IssuerKeys.from_private_hex(data["private_hex"])
    keys = IssuerKeys.generate()
    path.write_text(
        json.dumps({"private_hex": keys.export_private_hex(), "public_hex": keys.export_public_hex()}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return keys


def _load_records(sqlite_path: Path | None) -> list[dict]:
    if sqlite_path:
        conn = sqlite3.connect(str(sqlite_path))
        conn.row_factory = sqlite3.Row
        try:
            return records_from_sqlite(conn)
        finally:
            conn.close()
    conn = connect()
    migrate(conn)
    seed_mini_bundled(conn)
    try:
        return records_from_sqlite(conn)
    finally:
        conn.close()


def cmd_list_editions(_: argparse.Namespace) -> int:
    for sku, ed in editions().items():
        print(f"{sku.value:20} ${ed.list_price_usd:.2f}  {ed.title}")
        print(f"  {ed.protection_summary}")
    return 0


def _fulfilment_notes(*, provider: str, payment_ref: str, verified_by: str | None) -> str:
    payload = {
        "fulfilment": "manual",
        "payment_provider": provider,
        "external_payment_id": payment_ref,
        "verified_by": verified_by or "operator",
    }
    return json.dumps(payload, sort_keys=True)


def cmd_fulfil(args: argparse.Namespace) -> int:
    """Manual purchase → package → ledger after operator-verified payment.

    For 1–10 sales/week: no always-on licensing server required.
    """
    if not args.verified_payment:
        print(
            "Refusing fulfilment without --verified-payment. "
            "Confirm the transaction in the payment provider dashboard first "
            "(do not rely on customer-uploaded screenshots alone).",
            file=sys.stderr,
        )
        return 2

    sku_alias = args.sku.lower().strip()
    if sku_alias in {"dataset", "standard", "standard_dataset", "global_research_dataset"}:
        sku = SKU.STANDARD_DATASET
    elif sku_alias in {"studio", "academic_studio", "academic-studio"}:
        sku = SKU.ACADEMIC_STUDIO
    else:
        print(f"Unknown SKU alias: {args.sku} (use dataset|studio)", file=sys.stderr)
        return 2

    issuer = _issuer_from_env()
    records = _load_records(Path(args.sqlite) if args.sqlite else None)
    store = LicenseStore(app_data_dir() / "license_store.json", issuer)
    purchase = store.register_purchase(
        customer_id=args.customer,
        customer_email=args.email,
        sku=sku,
        payment_provider=args.provider,
        external_payment_id=args.payment_ref,
    )
    ctx = FingerprintContext(
        customer_id=args.customer,
        fingerprint_salt=purchase.fingerprint_salt,
        license_id=purchase.license_id,
    )
    ledger = DeliveryLedger(app_data_dir() / "delivery_ledger.sqlite")
    notes = _fulfilment_notes(
        provider=args.provider,
        payment_ref=args.payment_ref,
        verified_by=args.verified_by or "operator",
    )
    # Encode verification attestation into ledger notes
    notes_obj = json.loads(notes)
    notes_obj["payment_verified"] = True
    notes_obj["verification"] = "provider_dashboard"
    notes = json.dumps(notes_obj, sort_keys=True)
    out_dir = Path(args.out)
    if sku is SKU.STANDARD_DATASET:
        result = package_standard_dataset(
            records=records,
            out_dir=out_dir,
            ctx=ctx,
            issuer=issuer,
            ledger=ledger,
            customer_email=args.email,
            notes=notes,
        )
    else:
        device = load_or_create_device_identity() if args.activate else None
        result = build_protected_package(
            records=records,
            out_dir=out_dir,
            ctx=ctx,
            issuer=issuer,
            dek=purchase.dek,
            sku=sku,
            ledger=ledger,
            customer_email=args.email,
            activate_for_device=device,
            license_store=store if device else None,
            license_id=purchase.license_id if device else None,
            notes=notes,
        )
        if not args.activate:
            print(
                "Studio package built without CustomerLicense.aslic — "
                "customer activates on their device after delivery.",
                file=sys.stderr,
            )

    receipt = {
        "mode": "manual_fulfilment",
        "sku": sku.value,
        "customer_id": args.customer,
        "customer_email": args.email,
        "payment_provider": args.provider,
        "external_payment_id": args.payment_ref,
        "payment_verified": True,
        "license_id": purchase.license_id,
        "out_dir": str(out_dir.resolve()),
        "package": result,
        "delivery_sla": "Within 24 hours after payment clears (business days).",
        "next_steps": [
            "Re-check payment remains settled (no refund/chargeback).",
            "Deliver out_dir via private link (never a public identical marketplace file for datasets).",
            "For Studio, wait for activation_request.json then run issue-licence if offline.",
            "Keep delivery_ledger.sqlite and fulfilment_receipt.json backed up (operator only).",
        ],
    }
    receipt_path = out_dir / "fulfilment_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    # Operator-local durability: dated copies of ledger + license store (₹0 filesystem)
    from studio.licensing.ops_backup import backup_control_plane

    backup_meta = backup_control_plane(tag=f"fulfil-{purchase.license_id}")
    receipt["control_plane_backup"] = backup_meta
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    # Customer-safe instructions (no operator ledger secrets beyond licence id)
    customer_note = out_dir / "DELIVERY_INSTRUCTIONS.txt"
    customer_note.write_text(
        "Academic Outreach — delivery\n"
        "============================\n\n"
        f"Product: {sku.value}\n"
        f"Licence id: {purchase.license_id}\n"
        f"Customer: {args.email}\n\n"
        "Dataset buyers: open START_HERE.txt then GlobalResearch.xlsx.\n"
        "Studio buyers: install/open Academic Studio, open /activate, enter this licence id.\n"
        "If the seller uses offline activation, download an activation request and email it back.\n\n"
        "Do not publish this folder. Support uses your payment reference + this licence id.\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2))
    return 0


def cmd_issue_licence(args: argparse.Namespace) -> int:
    """Issue CustomerLicense.aslic from a customer activation_request.json (Option A)."""
    from studio.licensing.activation import ActivationRequest, activate_device
    from studio.licensing.crypto import b64d

    req_path = Path(args.request)
    data = json.loads(req_path.read_text(encoding="utf-8"))
    license_id = args.license_id or data.get("license_id")
    if not license_id:
        print("licence id required (--license-id or inside request JSON)", file=sys.stderr)
        return 2

    issuer = _issuer_from_env()
    store = LicenseStore(app_data_dir() / "license_store.json", issuer)
    rec = store.get(license_id)
    if not rec:
        print(f"Unknown licence {license_id} — fulfil the purchase first.", file=sys.stderr)
        return 2

    request = ActivationRequest(
        license_id=license_id,
        device_id=data["device_id"],
        device_fingerprint=data["device_fingerprint"],
        ed25519_public=b64d(data["ed25519_public"]),
        x25519_public=b64d(data["x25519_public"]),
        challenge=b64d(data["challenge"]),
        challenge_signature=b64d(data["challenge_signature"]),
        nonce=data["nonce"],
        requested_at=int(data["requested_at"]),
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        ent = activate_device(
            store,
            request,
            aslic_path=out,
            replace_device_id=args.replace_device_id,
        )
    except PermissionError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "license_id": ent.license_id,
                "device_id": request.device_id,
                "aslic": str(out.resolve()),
                "expires_at": ent.expires_at,
            },
            indent=2,
        )
    )
    return 0


def cmd_package_standard(args: argparse.Namespace) -> int:
    issuer = _issuer_from_env()
    records = _load_records(Path(args.sqlite) if args.sqlite else None)
    store = LicenseStore(app_data_dir() / "license_store.json", issuer)
    purchase = store.register_purchase(
        customer_id=args.customer,
        customer_email=args.email,
        sku=SKU.STANDARD_DATASET,
    )
    ctx = FingerprintContext(
        customer_id=args.customer,
        fingerprint_salt=purchase.fingerprint_salt,
        license_id=purchase.license_id,
    )
    ledger = DeliveryLedger(app_data_dir() / "delivery_ledger.sqlite")
    result = package_standard_dataset(
        records=records,
        out_dir=Path(args.out),
        ctx=ctx,
        issuer=issuer,
        ledger=ledger,
        customer_email=args.email,
    )
    print(json.dumps(result, indent=2))
    return 0


def cmd_sample_pack(args: argparse.Namespace) -> int:
    from studio.dataset.sample_pack import write_sample_pack

    records = _load_records(Path(args.sqlite) if args.sqlite else None)
    result = write_sample_pack(
        records,
        Path(args.out),
        n=args.n,
        redact_emails=args.redact_emails,
    )
    print(json.dumps(result, indent=2))
    return 0


def cmd_package_protected(args: argparse.Namespace) -> int:
    issuer = _issuer_from_env()
    records = _load_records(Path(args.sqlite) if args.sqlite else None)
    sku = SKU.ACADEMIC_STUDIO if args.studio else SKU.PROTECTED_DATASET
    store = LicenseStore(app_data_dir() / "license_store.json", issuer)
    purchase = store.register_purchase(
        customer_id=args.customer,
        customer_email=args.email,
        sku=sku,
    )
    ctx = FingerprintContext(
        customer_id=args.customer,
        fingerprint_salt=purchase.fingerprint_salt,
        license_id=purchase.license_id,
    )
    ledger = DeliveryLedger(app_data_dir() / "delivery_ledger.sqlite")
    device = load_or_create_device_identity() if args.activate else None
    result = build_protected_package(
        records=records,
        out_dir=Path(args.out),
        ctx=ctx,
        issuer=issuer,
        dek=purchase.dek,
        sku=sku,
        ledger=ledger,
        customer_email=args.email,
        activate_for_device=device,
        license_store=store if device else None,
        license_id=purchase.license_id if device else None,
    )
    print(json.dumps(result, indent=2))
    if not args.activate:
        print(
            "Package built without CustomerLicense.aslic — run activation after purchase verification.",
            file=sys.stderr,
        )
    return 0


def cmd_read(args: argparse.Namespace) -> int:
    issuer = _issuer_from_env()
    session = activate_local_catalog(
        Path(args.package),
        issuer_public_hex=issuer.export_public_hex(),
    )
    rows = session.search(query=args.query, university=args.university, limit=args.limit)
    print(json.dumps({"record_count": session.record_count(), "hits": rows}, indent=2))
    return 0


def cmd_device_info(_: argparse.Namespace) -> int:
    device = load_or_create_device_identity()
    print(json.dumps(device.public_record(), indent=2))
    return 0


def cmd_forensic(args: argparse.Namespace) -> int:
    from studio.dataset.forensic import inspect_path
    from studio.licensing.service import delivery_ledger

    report = inspect_path(Path(args.path), delivery_ledger())
    print(json.dumps(report.to_dict(), indent=2))
    return 0


def cmd_monitor(args: argparse.Namespace) -> int:
    from studio.licensing.monitor import (
        append_findings_log,
        default_leak_queries,
        github_code_search_urls,
        scan_local_corpus,
        scan_public_urls,
    )
    from studio.licensing.service import delivery_ledger

    ledger = delivery_ledger()
    findings = []
    if getattr(args, "path", None):
        findings.extend(scan_local_corpus([Path(p) for p in args.path], ledger))
    if getattr(args, "url", None):
        findings.extend(scan_public_urls(list(args.url), ledger))
    search_urls = []
    if getattr(args, "github_search", False):
        for q in default_leak_queries():
            search_urls.extend(github_code_search_urls(q))
    log_path = Path(args.log) if args.log else app_data_dir() / "piracy_findings.json"
    append_findings_log(log_path, findings)
    print(
        json.dumps(
            {
                "findings": len(findings),
                "log": str(log_path),
                "github_search_urls": search_urls,
                "items": [f.to_dict() for f in findings],
                "notice": "Hits are candidates for human review — never auto-accuse.",
            },
            indent=2,
        )
    )
    return 0


def cmd_issuer_vault(args: argparse.Namespace) -> int:
    from studio.licensing.crypto import IssuerKeys
    from studio.licensing.issuer_vault import default_vault_path, load_vault, write_vault

    path = Path(args.path) if args.path else default_vault_path()
    if args.init:
        keys = IssuerKeys.generate()
        write_vault(keys, args.passphrase, path)
        print(
            json.dumps(
                {
                    "ok": True,
                    "path": str(path),
                    "public_hex": keys.export_public_hex(),
                    "notice": "Store passphrase offline; set STUDIO_ISSUER_VAULT_PASSPHRASE to unlock",
                },
                indent=2,
            )
        )
        return 0
    keys = load_vault(args.passphrase, path)
    print(json.dumps({"ok": True, "path": str(path), "public_hex": keys.export_public_hex()}, indent=2))
    return 0


def cmd_sign_update(args: argparse.Namespace) -> int:
    from studio.licensing.service import issuer_keys
    from studio.licensing.updates import build_update_manifest, write_signed_update_manifest

    issuer = issuer_keys()
    manifest = build_update_manifest(
        version=args.version,
        channel=args.channel,
        payload_path=Path(args.payload),
        payload_url=args.url,
        min_version=args.min_version,
        release_notes=args.notes or "",
    )
    man, sig = write_signed_update_manifest(Path(args.out), manifest, issuer)
    print(json.dumps({"manifest": str(man), "signature": str(sig), "version": args.version}, indent=2))
    return 0


def cmd_extract_aspkg(args: argparse.Namespace) -> int:
    from studio.dataset.package_cipher import extract_aspkg
    from studio.licensing.crypto import b64d

    key = b64d(args.key_b64) if args.key_b64 else bytes.fromhex(args.key_hex)
    members = extract_aspkg(Path(args.aspkg), Path(args.out), key)
    print(json.dumps({"extracted": members, "out": args.out}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m studio.dataset")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("editions", help="List commercial editions")
    p.set_defaults(func=cmd_list_editions)

    p = sub.add_parser("device", help="Show this machine's licensing device identity")
    p.set_defaults(func=cmd_device_info)

    p = sub.add_parser(
        "fulfil",
        help="Manual fulfilment: verified payment → personalized package + ledger receipt",
    )
    p.add_argument("--sku", required=True, help="dataset | studio")
    p.add_argument("--out", required=True)
    p.add_argument("--customer", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--provider", required=True, help="paypal | fastspring | cashfree | …")
    p.add_argument("--payment-ref", required=True, help="Provider transaction / order id")
    p.add_argument("--verified-by", help="Operator identity for the receipt")
    p.add_argument(
        "--verified-payment",
        action="store_true",
        help="Required: attest you verified the payment in the provider dashboard",
    )
    p.add_argument("--sqlite", help="Optional source SQLite; default mini/bundled studio DB")
    p.add_argument(
        "--activate",
        action="store_true",
        help="Studio only: activate for this machine (ops/testing; not customer delivery)",
    )
    p.set_defaults(func=cmd_fulfil)

    p = sub.add_parser(
        "issue-licence",
        help="Issue CustomerLicense.aslic from a customer activation_request.json",
    )
    p.add_argument("--request", required=True, help="Path to activation_request.json")
    p.add_argument("--out", required=True, help="Output CustomerLicense.aslic path")
    p.add_argument("--license-id", help="Override licence id if not in request")
    p.add_argument("--replace-device-id", help="Drop a previous device slot")
    p.set_defaults(func=cmd_issue_licence)

    p = sub.add_parser("package-standard", help="Build fingerprinted Standard Dataset package")
    p.add_argument("--out", required=True)
    p.add_argument("--customer", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--sqlite", help="Optional source SQLite; default mini/bundled studio DB")
    p.set_defaults(func=cmd_package_standard)

    p = sub.add_parser(
        "sample-pack",
        help="Write a redistributable 20-25 record sample (xlsx + csv) for marketplace preview",
    )
    p.add_argument("--out", required=True)
    p.add_argument("--sqlite", help="Optional source SQLite; default mini/bundled studio DB")
    p.add_argument("-n", type=int, default=25, help="Sample size (default 25)")
    p.add_argument("--redact-emails", action="store_true", help="Partially mask email addresses")
    p.set_defaults(func=cmd_sample_pack)

    p = sub.add_parser("package-protected", help="Build encrypted Protected Dataset / Studio package")
    p.add_argument("--out", required=True)
    p.add_argument("--customer", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--sqlite", help="Optional source SQLite")
    p.add_argument("--studio", action="store_true", help="SKU academic_studio instead of protected_dataset")
    p.add_argument("--activate", action="store_true", help="Activate for this device and write .aslic")
    p.set_defaults(func=cmd_package_protected)

    p = sub.add_parser("read", help="Query an activated protected package")
    p.add_argument("--package", required=True)
    p.add_argument("--query")
    p.add_argument("--university")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_read)

    p = sub.add_parser(
        "monitor",
        help="Scan local corpus and/or allowlisted public URLs for piracy markers",
    )
    p.add_argument("--path", action="append", default=[], help="File or directory (repeatable)")
    p.add_argument("--url", action="append", default=[], help="Allowlisted public URL (repeatable)")
    p.add_argument(
        "--github-search",
        action="store_true",
        help="Emit public GitHub code-search URLs for default leak queries",
    )
    p.add_argument("--log", help="Findings JSON log path")
    p.set_defaults(func=cmd_monitor)

    p = sub.add_parser("issuer-vault", help="Create or unlock passphrase-encrypted issuer key vault")
    p.add_argument("--passphrase", required=True)
    p.add_argument("--path", help="Vault file path (default under STUDIO_DATA_DIR)")
    p.add_argument("--init", action="store_true", help="Generate new keys into vault")
    p.set_defaults(func=cmd_issuer_vault)

    p = sub.add_parser("sign-update", help="Sign an update payload manifest with the issuer key")
    p.add_argument("--payload", required=True, help="Update archive/binary path")
    p.add_argument("--url", required=True, help="Public download URL for the payload")
    p.add_argument("--version", required=True)
    p.add_argument("--out", required=True, help="Output directory for manifest + signature")
    p.add_argument("--channel", default="stable")
    p.add_argument("--min-version", default="0.0.0")
    p.add_argument("--notes", default="")
    p.set_defaults(func=cmd_sign_update)

    p = sub.add_parser(
        "forensic",
        help="Inspect a suspected leak package/folder (human-review report; never auto-accuse)",
    )
    p.add_argument("--path", required=True, help="File, folder, or zip to inspect")
    p.set_defaults(func=cmd_forensic)

    p = sub.add_parser("extract-aspkg", help="Extract AES-GCM .aspkg with package/DEK key")
    p.add_argument("--aspkg", required=True)
    p.add_argument("--out", required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--key-hex")
    g.add_argument("--key-b64")
    p.set_defaults(func=cmd_extract_aspkg)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
