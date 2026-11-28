"""Signed .aslic entitlement files (offline-capable, time-bounded)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from studio.licensing.crypto import (
    IssuerKeys,
    b64d,
    b64e,
    open_sealed_x25519,
    seal_to_x25519,
    sign_ed25519,
    verify_ed25519,
)
from studio.licensing.device import DeviceIdentity
from studio.licensing.products import SKU


ASLIC_VERSION = 1


@dataclass
class Entitlement:
    version: int
    license_id: str
    customer_id: str
    sku: str
    device_id: str
    device_fingerprint: str
    issued_at: int
    expires_at: int
    max_devices: int
    wrapped_dek: bytes
    features: dict[str, Any]
    nonce: str

    def payload_bytes(self) -> bytes:
        body = {
            "version": self.version,
            "license_id": self.license_id,
            "customer_id": self.customer_id,
            "sku": self.sku,
            "device_id": self.device_id,
            "device_fingerprint": self.device_fingerprint,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "max_devices": self.max_devices,
            "wrapped_dek": b64e(self.wrapped_dek),
            "features": self.features,
            "nonce": self.nonce,
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def to_dict(self) -> dict:
        return json.loads(self.payload_bytes())

    def unwrap_dek(self, device: DeviceIdentity) -> bytes:
        if device.device_id != self.device_id:
            raise PermissionError("Entitlement is bound to a different device_id")
        if device.fingerprint != self.device_fingerprint:
            raise PermissionError("Entitlement fingerprint mismatch")
        return open_sealed_x25519(device.x25519_key(), self.wrapped_dek)

    def is_expired(self, now: int | None = None) -> bool:
        now = int(time.time()) if now is None else now
        if self.issued_at > now + 300:
            # Clock rolled back significantly
            return True
        return now > self.expires_at


def issue_entitlement(
    *,
    issuer: IssuerKeys,
    license_id: str,
    customer_id: str,
    sku: SKU | str,
    device: DeviceIdentity,
    dek: bytes,
    ttl_seconds: int = 30 * 24 * 3600,
    max_devices: int = 2,
    features: dict[str, Any] | None = None,
    nonce: str | None = None,
    now: int | None = None,
) -> tuple[Entitlement, bytes]:
    """Return (entitlement, signature). DEK is sealed to the device X25519 key."""
    import secrets

    now = int(time.time()) if now is None else now
    sku_value = sku.value if isinstance(sku, SKU) else str(sku)
    ent = Entitlement(
        version=ASLIC_VERSION,
        license_id=license_id,
        customer_id=customer_id,
        sku=sku_value,
        device_id=device.device_id,
        device_fingerprint=device.fingerprint,
        issued_at=now,
        expires_at=now + int(ttl_seconds),
        max_devices=max_devices,
        wrapped_dek=seal_to_x25519(device.x25519_public, dek),
        features=features or {},
        nonce=nonce or secrets.token_hex(16),
    )
    sig = sign_ed25519(issuer.private, ent.payload_bytes())
    return ent, sig


def write_aslic(path: Path, entitlement: Entitlement, signature: bytes, issuer_public_hex: str) -> None:
    doc = {
        "format": "academic-studio-license",
        "alg": "aes-256-gcm+x25519+ed25519",
        "issuer_public": issuer_public_hex,
        "entitlement": entitlement.to_dict(),
        "sig": b64e(signature),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def read_aslic(path: Path, *, expected_issuer_public: bytes | None = None) -> Entitlement:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("format") != "academic-studio-license":
        raise ValueError("Not an Academic Studio licence file")
    issuer_pub = bytes.fromhex(doc["issuer_public"])
    if expected_issuer_public is not None and issuer_pub != expected_issuer_public:
        raise PermissionError("Licence issuer public key mismatch")
    ent_raw = doc["entitlement"]
    ent = Entitlement(
        version=int(ent_raw["version"]),
        license_id=ent_raw["license_id"],
        customer_id=ent_raw["customer_id"],
        sku=ent_raw["sku"],
        device_id=ent_raw["device_id"],
        device_fingerprint=ent_raw["device_fingerprint"],
        issued_at=int(ent_raw["issued_at"]),
        expires_at=int(ent_raw["expires_at"]),
        max_devices=int(ent_raw["max_devices"]),
        wrapped_dek=b64d(ent_raw["wrapped_dek"]),
        features=dict(ent_raw.get("features") or {}),
        nonce=ent_raw["nonce"],
    )
    sig = b64d(doc["sig"])
    if not verify_ed25519(issuer_pub, ent.payload_bytes(), sig):
        raise PermissionError("Licence signature invalid")
    if ent.is_expired():
        raise PermissionError("Licence entitlement expired — revalidate online")
    return ent
