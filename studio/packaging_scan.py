"""Fail the installer / customer package build if secrets sneak in."""

from __future__ import annotations

import sys
from pathlib import Path

FORBIDDEN_NAMES = {
    ".env",
    "dev_issuer.json",
    "license_store.json",
    "secrets.json",
    "cipher_license",
}

FORBIDDEN_SUFFIXES = (".env", ".pem")

FORBIDDEN_CONTENT_MARKERS = (
    "STUDIO_ISSUER_PRIVATE_HEX",
    "BEGIN PRIVATE KEY",
    "wrapped_dek_plaintext",
)


def scan_package_dir(root: Path) -> None:
    bad: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root))
        name = path.name
        if name in FORBIDDEN_NAMES or name.endswith(".env"):
            bad.append(f"{rel} (forbidden name)")
            continue
        if name.endswith(FORBIDDEN_SUFFIXES) and name != "manifest.sig":
            # allow .sig; block .pem
            if name.endswith(".pem"):
                bad.append(f"{rel} (forbidden suffix)")
                continue
        # Skip large binary catalogs for content scan
        if path.suffix.lower() in {
            ".asdb",
            ".aspkg",
            ".sqlite",
            ".xlsx",
            ".pdf",
            ".png",
            ".jpg",
        }:
            continue
        if path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for marker in FORBIDDEN_CONTENT_MARKERS:
            if marker in text:
                bad.append(f"{rel} (contains {marker})")
                break
    if bad:
        print("Package scan failed:", ", ".join(bad), file=sys.stderr)
        raise SystemExit(1)
    print("Package scan ok")


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    scan_package_dir(root)


if __name__ == "__main__":
    main()
