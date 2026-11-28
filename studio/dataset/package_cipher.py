"""Outer AES-256-GCM package container (.aspkg) around catalog payloads.

SQLCipher protects the database pages; this layer wraps asdb + docs + manifest
for transit so a casual file copy of ResearchCatalog.asdb alone is still keyed.
The package key is typically the same DEK sealed to the device in .aslic.
"""

from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

from studio.licensing.crypto import aes_gcm_decrypt, aes_gcm_encrypt

ASPKG_MAGIC = b"ASPKG1\0"
INCLUDE_NAMES = (
    "ResearchCatalog.asdb",
    "Documentation.txt",
    "Documentation.pdf",
    "manifest.json",
    "manifest.sig",
    "README.txt",
)


def build_aspkg(package_dir: Path, out_path: Path, package_key: bytes) -> dict:
    if len(package_key) != 32:
        raise ValueError("package_key must be 32 bytes")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name in INCLUDE_NAMES:
            path = package_dir / name
            if path.exists():
                tar.add(path, arcname=name)
    plaintext = buf.getvalue()
    if not plaintext:
        raise ValueError("Nothing to package — missing ResearchCatalog.asdb?")
    blob = aes_gcm_encrypt(package_key, plaintext, aad=b"academic-studio/aspkg-v1")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(ASPKG_MAGIC + blob)
    return {
        "path": str(out_path),
        "bytes": out_path.stat().st_size,
        "members": [n for n in INCLUDE_NAMES if (package_dir / n).exists()],
    }


def extract_aspkg(aspkg_path: Path, out_dir: Path, package_key: bytes) -> list[str]:
    raw = aspkg_path.read_bytes()
    if not raw.startswith(ASPKG_MAGIC):
        raise ValueError("Not an .aspkg container")
    plaintext = aes_gcm_decrypt(
        package_key, raw[len(ASPKG_MAGIC) :], aad=b"academic-studio/aspkg-v1"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    members: list[str] = []
    with tarfile.open(fileobj=io.BytesIO(plaintext), mode="r:gz") as tar:
        # Safe extract: only allow bare filenames from allowlist
        for member in tar.getmembers():
            name = Path(member.name).name
            if name not in INCLUDE_NAMES:
                continue
            if not member.isfile():
                continue
            target = out_dir / name
            with tar.extractfile(member) as src, target.open("wb") as dst:
                assert src is not None
                dst.write(src.read())
            members.append(name)
    meta = {"extracted": members}
    (out_dir / ".aspkg_extract.json").write_text(json.dumps(meta, indent=2) + "\n")
    return members
