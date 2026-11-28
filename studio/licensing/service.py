"""Process-local licensing service accessors (issuer, store, ledger)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from studio.licensing.activation import LicenseStore
from studio.licensing.crypto import IssuerKeys
from studio.licensing.issuer_vault import (
    default_vault_path,
    ensure_production_ready,
    issuer_mode,
    load_vault,
)
from studio.licensing.ledger import DeliveryLedger
from studio.paths import app_data_dir


def issuer_keys() -> IssuerKeys:
    """Resolve issuer signing keys.

    Precedence:
    1. ``STUDIO_ISSUER_PRIVATE_HEX`` (CI / sealed env)
    2. Passphrase vault (``STUDIO_ISSUER_VAULT_PASSPHRASE`` + vault file)
    3. Dev-only auto ``dev_issuer.json`` (forbidden when ``STUDIO_ISSUER_MODE=production``)
    """
    ensure_production_ready()

    hex_key = os.environ.get("STUDIO_ISSUER_PRIVATE_HEX", "").strip()
    if hex_key:
        return IssuerKeys.from_private_hex(hex_key)

    passphrase = os.environ.get("STUDIO_ISSUER_VAULT_PASSPHRASE", "").strip()
    vault_path = default_vault_path()
    if passphrase and vault_path.is_file():
        return load_vault(passphrase, vault_path)

    if issuer_mode() == "production":
        # ensure_production_ready should have caught this; belt-and-suspenders
        raise RuntimeError("Production issuer keys unavailable")

    path = app_data_dir() / "dev_issuer.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return IssuerKeys.from_private_hex(data["private_hex"])
    keys = IssuerKeys.generate()
    path.write_text(
        json.dumps(
            {
                "private_hex": keys.export_private_hex(),
                "public_hex": keys.export_public_hex(),
                "notice": "DEV ONLY — never ship in customer packages; prefer issuer_vault in production",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    os.chmod(path, 0o600)
    return keys


def license_store() -> LicenseStore:
    return LicenseStore(app_data_dir() / "license_store.json", issuer_keys())


def delivery_ledger() -> DeliveryLedger:
    return DeliveryLedger(app_data_dir() / "delivery_ledger.sqlite")


def webhook_secret() -> str | None:
    return os.environ.get("STUDIO_LICENSING_WEBHOOK_SECRET")


def payment_events_path() -> Path:
    return app_data_dir() / "payment_events.jsonl"
