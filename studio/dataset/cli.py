"""CLI for packaging and activating dataset deliveries.

Examples:
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


def cmd_monitor(args: argparse.Namespace) -> int:
    from studio.licensing.monitor import append_findings_log, scan_local_corpus
    from studio.licensing.service import delivery_ledger

    paths = [Path(p) for p in args.path]
    findings = scan_local_corpus(paths, delivery_ledger())
    log_path = Path(args.log) if args.log else app_data_dir() / "piracy_findings.json"
    append_findings_log(log_path, findings)
    print(json.dumps({"findings": len(findings), "log": str(log_path), "items": [f.to_dict() for f in findings]}, indent=2))
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

    p = sub.add_parser("package-standard", help="Build fingerprinted Standard Dataset package")
    p.add_argument("--out", required=True)
    p.add_argument("--customer", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--sqlite", help="Optional source SQLite; default mini/bundled studio DB")
    p.set_defaults(func=cmd_package_standard)

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

    p = sub.add_parser("monitor", help="Scan local corpus for piracy markers (ledger compare)")
    p.add_argument("--path", action="append", required=True, help="File or directory (repeatable)")
    p.add_argument("--log", help="Findings JSON log path")
    p.set_defaults(func=cmd_monitor)

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
