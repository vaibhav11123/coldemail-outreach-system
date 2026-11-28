"""Cryptographic device identity (Ed25519 + X25519), not MAC-address locking.

See ``device_backend.py`` for binding-mode honesty: current keys are software- or
keyring-backed and exportable unless a hardware adapter is implemented.
"""

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
from studio.licensing.device_backend import (
    BindingMode,
    describe_device_security,
    identity_envelope,
    select_device_backend,
    unwrap_identity_envelope,
)

DEVICE_SECRET_NAME = "licensing.device_identity.v1"


@dataclass
class DeviceIdentity:
    device_id: str
    fingerprint: str
    ed25519_private: bytes
    ed25519_public: bytes
    x25519_private: bytes
    x25519_public: bytes
    binding: BindingMode = BindingMode.SOFTWARE
    backend_id: str = "software-file-v1"

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
            "binding": self.binding.value,
            "backend_id": self.backend_id,
            "exportable_private_keys": self.binding != BindingMode.HARDWARE,
            "security": describe_device_security(),
        }

    def to_storage(self) -> str:
        inner = json.dumps(
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
        return identity_envelope(
            inner, binding=self.binding, backend_id=self.backend_id
        )

    @classmethod
    def from_storage(cls, raw: str) -> DeviceIdentity:
        flat, binding, backend_id = unwrap_identity_envelope(raw)
        data = json.loads(flat)
        return cls(
            device_id=data["device_id"],
            fingerprint=data["fingerprint"],
            ed25519_private=b64d(data["ed25519_private"]),
            ed25519_public=b64d(data["ed25519_public"]),
            x25519_private=b64d(data["x25519_private"]),
            x25519_public=b64d(data["x25519_public"]),
            binding=binding,
            backend_id=backend_id,
        )


def _fingerprint_from_keys(ed_pub: bytes, x_pub: bytes, device_id: str) -> str:
    h = hashlib.sha256()
    h.update(b"academic-studio/device-v1\0")
    h.update(device_id.encode("utf-8"))
    h.update(ed_pub)
    h.update(x_pub)
    return h.hexdigest()


def create_device_identity() -> DeviceIdentity:
    backend = select_device_backend()
    caps = backend.capabilities()
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
        binding=caps.binding,
        backend_id=caps.backend_id,
    )


def load_or_create_device_identity() -> DeviceIdentity:
    backend = select_device_backend()
    existing = backend.load_blob(DEVICE_SECRET_NAME)
    if existing:
        return DeviceIdentity.from_storage(existing)
    identity = create_device_identity()
    backend.store_blob(DEVICE_SECRET_NAME, identity.to_storage())
    return identity
