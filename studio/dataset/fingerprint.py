"""Forensic fingerprinting that does not alter factual faculty fields.

Canonical researcher identity stays internal. Each buyer gets a consistent set of
surrogate export IDs derived via HMAC. Leaked IDs can be matched to a delivery
ledger; matching is evidence, not automatic accusation.
"""

from __future__ import annotations

import hashlib
import hmac
import random
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class FingerprintContext:
    customer_id: str
    fingerprint_salt: str
    license_id: str

    @property
    def material(self) -> bytes:
        return f"{self.customer_id}|{self.license_id}|{self.fingerprint_salt}".encode(
            "utf-8"
        )


def export_id_for(ctx: FingerprintContext, canonical_id: str) -> str:
    """Stable per-customer surrogate ID. Never rewrite names/emails/pubs."""
    digest = hmac.new(
        ctx.material,
        f"export-id-v1:{canonical_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"R-{digest[:8].upper()}"


def order_seed(ctx: FingerprintContext) -> int:
    digest = hmac.new(ctx.material, b"row-order-v1", hashlib.sha256).hexdigest()
    return int(digest[:16], 16)


def permute_rows(rows: list[T], ctx: FingerprintContext) -> list[T]:
    """Customer-specific row order. Lost when the buyer sorts — still useful raw."""
    out = list(rows)
    rng = random.Random(order_seed(ctx))
    rng.shuffle(out)
    return out


def visible_licence_banner(ctx: FingerprintContext) -> str:
    return (
        f"Licensed to customer {ctx.customer_id} · licence {ctx.license_id} · "
        "redistribution prohibited under the purchase terms."
    )


def provenance_payload(ctx: FingerprintContext, delivery_id: str | None = None) -> dict:
    return {
        "product": "Global Research Dataset",
        "customer_id": ctx.customer_id,
        "license_id": ctx.license_id,
        "delivery_id": delivery_id,
        "fingerprint_scheme": "hmac-sha256-v1",
        "notice": (
            "This delivery is personalized. Export IDs are customer-specific and "
            "do not appear in other customers' copies. Do not share machine-readable "
            "exports outside your licensed use."
        ),
    }
