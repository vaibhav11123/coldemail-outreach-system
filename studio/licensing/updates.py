"""Signed software update manifests (issuer Ed25519).

Customer apps verify ``update_manifest.json`` + ``update_manifest.sig`` before
applying an update payload. Signing uses the same issuer key as licences —
customers need only the public key (already shipped in packages).

This does **not** replace OS code-signing (Authenticode / Apple notarization).
It provides an application-level authenticity check for update channels that
distribute zip/AppImage payloads from marketplace mirrors or R2.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from studio.licensing.crypto import IssuerKeys, b64d, b64e, sign_ed25519, verify_ed25519


MANIFEST_NAME = "update_manifest.json"
SIG_NAME = "update_manifest.sig"


def build_update_manifest(
    *,
    version: str,
    channel: str,
    payload_path: Path,
    payload_url: str,
    min_version: str | None = None,
    release_notes: str = "",
) -> dict[str, Any]:
    data = payload_path.read_bytes()
    return {
        "v": 1,
        "product": "academic_studio",
        "version": version,
        "channel": channel,
        "min_version": min_version or "0.0.0",
        "payload_url": payload_url,
        "payload_sha256": hashlib.sha256(data).hexdigest(),
        "payload_bytes": len(data),
        "payload_name": payload_path.name,
        "release_notes": release_notes,
    }


def sign_update_manifest(manifest: dict[str, Any], issuer: IssuerKeys) -> bytes:
    body = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sign_ed25519(issuer.private, body)


def write_signed_update_manifest(
    out_dir: Path,
    manifest: dict[str, Any],
    issuer: IssuerKeys,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    man_path = out_dir / MANIFEST_NAME
    sig_path = out_dir / SIG_NAME
    man_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    sig = sign_update_manifest(manifest, issuer)
    sig_path.write_text(b64e(sig) + "\n", encoding="utf-8")
    return man_path, sig_path


def verify_update_manifest(
    manifest: dict[str, Any],
    signature_b64: str,
    issuer_public_hex: str,
) -> bool:
    body = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return verify_ed25519(bytes.fromhex(issuer_public_hex), body, b64d(signature_b64.strip()))


def verify_payload_file(manifest: dict[str, Any], payload_path: Path) -> bool:
    data = payload_path.read_bytes()
    if len(data) != int(manifest.get("payload_bytes") or -1):
        return False
    return hashlib.sha256(data).hexdigest() == manifest.get("payload_sha256")
