"""Ed25519 signatures, AES-256-GCM, and X25519 sealed DEK wrapping."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64d(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def generate_ed25519() -> tuple[Ed25519PrivateKey, bytes]:
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return priv, pub


def generate_x25519() -> tuple[X25519PrivateKey, bytes]:
    priv = X25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return priv, pub


def ed25519_private_from_bytes(raw: bytes) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(raw)


def ed25519_public_from_bytes(raw: bytes) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(raw)


def x25519_private_from_bytes(raw: bytes) -> X25519PrivateKey:
    return X25519PrivateKey.from_private_bytes(raw)


def x25519_public_from_bytes(raw: bytes) -> X25519PublicKey:
    return X25519PublicKey.from_public_bytes(raw)


def private_bytes_ed25519(priv: Ed25519PrivateKey) -> bytes:
    return priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )


def private_bytes_x25519(priv: X25519PrivateKey) -> bytes:
    return priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )


def sign_ed25519(priv: Ed25519PrivateKey, message: bytes) -> bytes:
    return priv.sign(message)


def verify_ed25519(pub: bytes | Ed25519PublicKey, message: bytes, signature: bytes) -> bool:
    key = pub if isinstance(pub, Ed25519PublicKey) else ed25519_public_from_bytes(pub)
    try:
        key.verify(signature, message)
        return True
    except Exception:
        return False


def aes_gcm_encrypt(key: bytes, plaintext: bytes, aad: bytes | None = None) -> bytes:
    if len(key) != 32:
        raise ValueError("AES-256-GCM requires a 32-byte key")
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext, aad)
    return nonce + ct


def aes_gcm_decrypt(key: bytes, blob: bytes, aad: bytes | None = None) -> bytes:
    if len(key) != 32:
        raise ValueError("AES-256-GCM requires a 32-byte key")
    nonce, ct = blob[:12], blob[12:]
    return AESGCM(key).decrypt(nonce, ct, aad)


def seal_to_x25519(recipient_public: bytes, plaintext: bytes) -> bytes:
    """Ephemeral X25519 + HKDF-SHA256 + AES-256-GCM sealed blob."""
    eph_priv, eph_pub = generate_x25519()
    shared = eph_priv.exchange(x25519_public_from_bytes(recipient_public))
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"academic-studio/asdb-dek-v1",
    ).derive(shared)
    body = aes_gcm_encrypt(key, plaintext, aad=eph_pub)
    return eph_pub + body


def open_sealed_x25519(recipient_private: X25519PrivateKey, blob: bytes) -> bytes:
    eph_pub, body = blob[:32], blob[32:]
    shared = recipient_private.exchange(x25519_public_from_bytes(eph_pub))
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"academic-studio/asdb-dek-v1",
    ).derive(shared)
    return aes_gcm_decrypt(key, body, aad=eph_pub)


@dataclass(frozen=True)
class IssuerKeys:
    """Signing keys for manifests and .aslic files (server-side only)."""

    private: Ed25519PrivateKey
    public: bytes

    @classmethod
    def generate(cls) -> IssuerKeys:
        priv, pub = generate_ed25519()
        return cls(private=priv, public=pub)

    def export_public_hex(self) -> str:
        return self.public.hex()

    def export_private_hex(self) -> str:
        return private_bytes_ed25519(self.private).hex()

    @classmethod
    def from_private_hex(cls, hex_key: str) -> IssuerKeys:
        priv = ed25519_private_from_bytes(bytes.fromhex(hex_key))
        pub = priv.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return cls(private=priv, public=pub)
