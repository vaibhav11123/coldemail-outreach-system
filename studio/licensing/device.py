"""Cryptographic device identity (Ed25519 + X25519), not MAC-address locking."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from studio.licensing.crypto import (
    b64d,
    b64e,
    generate_ed25519,
    generate_x25519,
    private_bytes_ed25519,
    private_bytes_x25519,
    sign_ed25519,
    ed25519_private_from_bytes,
    x25519_private_from_bytes,
)
from studio.secrets_store import get_secret, set_secret

DEVICE_SECRET_NAME = "licensing.device_identity.v1"


@dataclass
class DeviceIdentity:
    device_id: str
    fingerprint: str
    ed25519_private: bytes
    ed25519_public: bytes
    x25519_private: bytes
    x25519_public: bytes

    def sign_challenge(self, challenge: bytes) -> bytes:
        return sign_ed25519(ed25519_private_from_bytes(self.ed25519_private), challenge)

    def x25519_key(self):
        return x25519_private_from_bytes(self.x25519_private)

    def public_record(self) -> dict:
        return {
            "device_id": self.device_id,
            "fingerprint": self.fingerprint,
            "ed25519_public": b64e(self.ed25519_public),
            "x25519_public": b64e(self.x25519_public),
        }

    def to_storage(self) -> str:
        return json.dumps(
            {
                "device_id": self.device_id,
                "fingerprint": self.fingerprint,
                "ed25519_private": b64e(self.ed25519_private),
                "ed25519_public": b64e(self.ed25519_public),
                "x25519_private": b64e(self.x25519_private),
                "x25519_public": b64e(self.x25519_public),
            },
            separators=(",", ":"),
        )

    @classmethod
    def from_storage(cls, raw: str) -> DeviceIdentity:
        data = json.loads(raw)
        return cls(
            device_id=data["device_id"],
            fingerprint=data["fingerprint"],
            ed25519_private=b64d(data["ed25519_private"]),
            ed25519_public=b64d(data["ed25519_public"]),
            x25519_private=b64d(data["x25519_private"]),
            x25519_public=b64d(data["x25519_public"]),
        )


def _fingerprint_from_keys(ed_pub: bytes, x_pub: bytes, device_id: str) -> str:
    h = hashlib.sha256()
    h.update(b"academic-studio/device-v1\0")
    h.update(device_id.encode("utf-8"))
    h.update(ed_pub)
    h.update(x_pub)
    return h.hexdigest()


def create_device_identity() -> DeviceIdentity:
    device_id = str(uuid.uuid4())
    ed_priv, ed_pub = generate_ed25519()
    x_priv, x_pub = generate_x25519()
    return DeviceIdentity(
        device_id=device_id,
        fingerprint=_fingerprint_from_keys(ed_pub, x_pub, device_id),
        ed25519_private=private_bytes_ed25519(ed_priv),
        ed25519_public=ed_pub,
        x25519_private=private_bytes_x25519(x_priv),
        x25519_public=x_pub,
    )


def load_or_create_device_identity() -> DeviceIdentity:
    existing = get_secret(DEVICE_SECRET_NAME)
    if existing:
        return DeviceIdentity.from_storage(existing)
    identity = create_device_identity()
    set_secret(DEVICE_SECRET_NAME, identity.to_storage())
    return identity
