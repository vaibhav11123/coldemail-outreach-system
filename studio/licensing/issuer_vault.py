"""Passphrase-encrypted issuer private key vault (operator control plane).

Zero fixed-cost design:
- No cloud KMS required.
- Operator sets STUDIO_ISSUER_VAULT_PASSPHRASE (and optional STUDIO_ISSUER_VAULT_PATH).
- Production mode (STUDIO_ISSUER_MODE=production) refuses auto-generated plaintext
  ``dev_issuer.json`` keys.

Format (JSON file, mode 0600)::

    {
      "v": 1,
      "kdf": "scrypt",
      "n": 16384, "r": 8, "p": 1,
      "salt_b64": "...",
      "blob_b64": "<aes-gcm(nonce||ct) of private_hex utf-8>",
      "public_hex": "..."
    }
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from studio.licensing.crypto import IssuerKeys, aes_gcm_decrypt, aes_gcm_encrypt, b64d, b64e
from studio.paths import app_data_dir

VAULT_AAD = b"academic-studio/issuer-vault-v1"


def default_vault_path() -> Path:
    env = os.environ.get("STUDIO_ISSUER_VAULT_PATH", "").strip()
    if env:
        return Path(env).expanduser()
    return app_data_dir() / "issuer_vault.json"


def _derive_key(passphrase: str, salt: bytes, *, n: int, r: int, p: int) -> bytes:
    return Scrypt(salt=salt, length=32, n=n, r=r, p=p).derive(passphrase.encode("utf-8"))


def write_vault(
    keys: IssuerKeys,
    passphrase: str,
    path: Path | None = None,
    *,
    n: int = 2**14,
    r: int = 8,
    p: int = 1,
) -> Path:
    if len(passphrase) < 12:
        raise ValueError("Vault passphrase must be at least 12 characters")
    path = path or default_vault_path()
    salt = os.urandom(16)
    key = _derive_key(passphrase, salt, n=n, r=r, p=p)
    blob = aes_gcm_encrypt(key, keys.export_private_hex().encode("utf-8"), aad=VAULT_AAD)
    doc = {
        "v": 1,
        "kdf": "scrypt",
        "n": n,
        "r": r,
        "p": p,
        "salt_b64": b64e(salt),
        "blob_b64": b64e(blob),
        "public_hex": keys.export_public_hex(),
        "notice": "OPERATOR ONLY — never ship in customer packages or public repos",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    return path


def load_vault(passphrase: str, path: Path | None = None) -> IssuerKeys:
    path = path or default_vault_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    if int(data.get("v", 0)) != 1 or data.get("kdf") != "scrypt":
        raise ValueError("Unsupported issuer vault format")
    salt = b64d(data["salt_b64"])
    key = _derive_key(
        passphrase,
        salt,
        n=int(data["n"]),
        r=int(data["r"]),
        p=int(data["p"]),
    )
    private_hex = aes_gcm_decrypt(key, b64d(data["blob_b64"]), aad=VAULT_AAD).decode("utf-8")
    keys = IssuerKeys.from_private_hex(private_hex)
    expected_pub = str(data.get("public_hex") or "")
    if expected_pub and expected_pub != keys.export_public_hex():
        raise ValueError("Vault public_hex mismatch after decrypt")
    return keys


def issuer_mode() -> str:
    return (os.environ.get("STUDIO_ISSUER_MODE") or "dev").strip().lower()


def ensure_production_ready() -> None:
    """Raise if production mode lacks a non-dev key source."""
    if issuer_mode() != "production":
        return
    if os.environ.get("STUDIO_ISSUER_PRIVATE_HEX", "").strip():
        return
    if os.environ.get("STUDIO_ISSUER_VAULT_PASSPHRASE", "").strip() and default_vault_path().is_file():
        return
    raise RuntimeError(
        "STUDIO_ISSUER_MODE=production requires STUDIO_ISSUER_PRIVATE_HEX or "
        "an unlockable issuer vault (STUDIO_ISSUER_VAULT_PASSPHRASE + vault file). "
        "Refusing auto-generated plaintext dev_issuer.json."
    )
