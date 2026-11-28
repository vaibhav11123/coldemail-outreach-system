"""Purchase → entitlement activation with challenge-response and device limits."""

from __future__ import annotations

import hashlib
import json
import secrets
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from studio.licensing.crypto import IssuerKeys, b64d, b64e, verify_ed25519
from studio.licensing.device import DeviceIdentity
from studio.licensing.entitlement import (
    Entitlement,
    issue_entitlement,
    write_aslic,
)
from studio.licensing.products import SKU, get_edition


@dataclass
class PurchaseRecord:
    license_id: str
    customer_id: str
    customer_email: str
    sku: str
    dek: bytes
    fingerprint_salt: str
    created_at: int
    revoked: bool = False
    activated_devices: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class ActivationRequest:
    license_id: str
    device_id: str
    device_fingerprint: str
    ed25519_public: bytes
    x25519_public: bytes
    challenge: bytes
    challenge_signature: bytes
    nonce: str
    requested_at: int

    def to_dict(self) -> dict:
        return {
            "license_id": self.license_id,
            "device_id": self.device_id,
            "device_fingerprint": self.device_fingerprint,
            "ed25519_public": b64e(self.ed25519_public),
            "x25519_public": b64e(self.x25519_public),
            "challenge": b64e(self.challenge),
            "challenge_signature": b64e(self.challenge_signature),
            "nonce": self.nonce,
            "requested_at": self.requested_at,
        }


class LicenseStore:
    """Local JSON store for issuer ops (manual fulfilment and local tests).

    Production path: keep this on the operator machine for low volume; optional
    Cloudflare Workers + D1 later. Do not subscribe to Keygen for ₹0 fixed cost.
    """

    def __init__(self, path: Path, issuer: IssuerKeys):
        self.path = path
        self.issuer = issuer
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"purchases": {}})

    def _read(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def find_by_external_payment_id(self, external_payment_id: str) -> PurchaseRecord | None:
        """Idempotency lookup for payment provider transaction ids."""
        if not external_payment_id:
            return None
        data = self._read()
        for raw in data.get("purchases", {}).values():
            if str(raw.get("external_payment_id") or "") == external_payment_id:
                return self.get(raw["license_id"])
        return None

    def register_purchase(
        self,
        *,
        customer_id: str,
        customer_email: str,
        sku: SKU | str,
        dek: bytes | None = None,
        fingerprint_salt: str | None = None,
        payment_provider: str | None = None,
        external_payment_id: str | None = None,
    ) -> PurchaseRecord:
        sku_value = sku.value if isinstance(sku, SKU) else str(sku)
        get_edition(sku_value)  # validate
        # Replay-safe: identical external_payment_id returns the existing entitlement
        if external_payment_id:
            existing = self.find_by_external_payment_id(external_payment_id)
            if existing:
                if existing.sku != sku_value:
                    raise ValueError(
                        f"external_payment_id already bound to sku={existing.sku}, not {sku_value}"
                    )
                return existing
        rec = PurchaseRecord(
            license_id=f"lic_{uuid.uuid4().hex[:16]}",
            customer_id=customer_id,
            customer_email=customer_email,
            sku=sku_value,
            dek=dek or secrets.token_bytes(32),
            fingerprint_salt=fingerprint_salt or secrets.token_hex(16),
            created_at=int(time.time()),
        )
        data = self._read()
        data["purchases"][rec.license_id] = {
            "license_id": rec.license_id,
            "customer_id": rec.customer_id,
            "customer_email": rec.customer_email,
            "sku": rec.sku,
            "dek": b64e(rec.dek),
            "fingerprint_salt": rec.fingerprint_salt,
            "created_at": rec.created_at,
            "revoked": False,
            "activated_devices": {},
            "payment_provider": payment_provider,
            "external_payment_id": external_payment_id,
            "used_nonces": [],
        }
        self._write(data)
        return rec

    def get(self, license_id: str) -> PurchaseRecord | None:
        raw = self._read()["purchases"].get(license_id)
        if not raw:
            return None
        return PurchaseRecord(
            license_id=raw["license_id"],
            customer_id=raw["customer_id"],
            customer_email=raw["customer_email"],
            sku=raw["sku"],
            dek=b64d(raw["dek"]),
            fingerprint_salt=raw["fingerprint_salt"],
            created_at=int(raw["created_at"]),
            revoked=bool(raw.get("revoked")),
            activated_devices=dict(raw.get("activated_devices") or {}),
        )

    def save(self, rec: PurchaseRecord) -> None:
        data = self._read()
        prev = dict(data.get("purchases", {}).get(rec.license_id) or {})
        data["purchases"][rec.license_id] = {
            **prev,
            "license_id": rec.license_id,
            "customer_id": rec.customer_id,
            "customer_email": rec.customer_email,
            "sku": rec.sku,
            "dek": b64e(rec.dek),
            "fingerprint_salt": rec.fingerprint_salt,
            "created_at": rec.created_at,
            "revoked": rec.revoked,
            "activated_devices": rec.activated_devices,
        }
        self._write(data)

    def revoke(self, license_id: str) -> None:
        rec = self.get(license_id)
        if not rec:
            raise KeyError(license_id)
        rec.revoked = True
        self.save(rec)


def build_activation_request(device: DeviceIdentity, license_id: str) -> ActivationRequest:
    nonce = secrets.token_hex(16)
    requested_at = int(time.time())
    challenge = hashlib.sha256(
        f"activate:{license_id}:{device.device_id}:{nonce}:{requested_at}".encode()
    ).digest()
    sig = device.sign_challenge(challenge)
    return ActivationRequest(
        license_id=license_id,
        device_id=device.device_id,
        device_fingerprint=device.fingerprint,
        ed25519_public=device.ed25519_public,
        x25519_public=device.x25519_public,
        challenge=challenge,
        challenge_signature=sig,
        nonce=nonce,
        requested_at=requested_at,
    )


def activate_device(
    store: LicenseStore,
    request: ActivationRequest,
    *,
    aslic_path: Path,
    ttl_seconds: int = 30 * 24 * 3600,
    replace_device_id: str | None = None,
) -> Entitlement:
    rec = store.get(request.license_id)
    if not rec:
        raise KeyError("Unknown licence")
    if rec.revoked:
        raise PermissionError("Licence revoked")

    if not verify_ed25519(
        request.ed25519_public, request.challenge, request.challenge_signature
    ):
        raise PermissionError("Device challenge signature invalid")

    expected = hashlib.sha256(
        f"activate:{request.license_id}:{request.device_id}:{request.nonce}:{request.requested_at}".encode()
    ).digest()
    if expected != request.challenge:
        raise PermissionError("Challenge mismatch (possible replay)")

    now = int(time.time())
    # Reject stale or far-future challenges (clock skew / replay window)
    if request.requested_at > now + 120:
        raise PermissionError("Activation challenge timestamp is in the future")
    if now - request.requested_at > 600:
        raise PermissionError("Activation challenge expired")

    edition = get_edition(rec.sku)
    if edition.max_devices <= 0:
        raise PermissionError("This SKU does not use device activation")

    # Nonce replay check before mutating device slots
    data = store._read()
    raw = data["purchases"].get(rec.license_id) or {}
    used = list(raw.get("used_nonces") or [])
    if request.nonce in used:
        raise PermissionError("Activation nonce already used (replay)")

    if replace_device_id and replace_device_id in rec.activated_devices:
        del rec.activated_devices[replace_device_id]

    if request.device_id not in rec.activated_devices:
        if len(rec.activated_devices) >= edition.max_devices:
            raise PermissionError(
                f"Device limit reached ({edition.max_devices}). Replace an existing device."
            )
        rec.activated_devices[request.device_id] = {
            "fingerprint": request.device_fingerprint,
            "activated_at": int(time.time()),
            "ed25519_public": b64e(request.ed25519_public),
            "x25519_public": b64e(request.x25519_public),
        }
    else:
        known = rec.activated_devices[request.device_id]
        if known["fingerprint"] != request.device_fingerprint:
            raise PermissionError("Device fingerprint changed — contact support for replacement")

    used.append(request.nonce)
    raw["used_nonces"] = used[-256:]
    data["purchases"][rec.license_id] = raw
    store._write(data)
    store.save(rec)

    # Reconstruct a DeviceIdentity-shaped object for sealing without private keys
    device_stub = DeviceIdentity(
        device_id=request.device_id,
        fingerprint=request.device_fingerprint,
        ed25519_private=b"",
        ed25519_public=request.ed25519_public,
        x25519_private=b"",
        x25519_public=request.x25519_public,
    )
    ent, sig = issue_entitlement(
        issuer=store.issuer,
        license_id=rec.license_id,
        customer_id=rec.customer_id,
        sku=rec.sku,
        device=device_stub,
        dek=rec.dek,
        ttl_seconds=ttl_seconds,
        max_devices=edition.max_devices,
        features={
            "encrypted_catalog": edition.encrypted_catalog,
            "studio_features": edition.includes_studio_features,
            # Studio includes machine-readable access inside the app; Reader CSV
            # still uses the controlled_export path (fingerprinted, limited).
            "controlled_exports": bool(
                edition.encrypted_catalog or not edition.machine_readable_exports
            ),
        },
        nonce=request.nonce,
    )
    write_aslic(aslic_path, ent, sig, store.issuer.export_public_hex())
    return ent
