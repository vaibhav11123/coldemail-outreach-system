"""Process-local licensing service accessors (issuer, store, ledger)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from studio.licensing.activation import LicenseStore
from studio.licensing.crypto import IssuerKeys
from studio.licensing.ledger import DeliveryLedger
from studio.paths import app_data_dir


def issuer_keys() -> IssuerKeys:
    hex_key = os.environ.get("STUDIO_ISSUER_PRIVATE_HEX")
    if hex_key:
        return IssuerKeys.from_private_hex(hex_key.strip())
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
                "notice": "DEV ONLY — never ship in customer packages",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return keys


def license_store() -> LicenseStore:
    return LicenseStore(app_data_dir() / "license_store.json", issuer_keys())


def delivery_ledger() -> DeliveryLedger:
    return DeliveryLedger(app_data_dir() / "delivery_ledger.sqlite")


def webhook_secret() -> str | None:
    return os.environ.get("STUDIO_LICENSING_WEBHOOK_SECRET")
