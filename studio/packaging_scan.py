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
    "cold_email_outreach_all_cleaned_ranked.csv",
    "delivery_ledger.sqlite",
    "payment_events.jsonl",
}

FORBIDDEN_NAME_SUBSTRINGS = (
    "cold_email_outreach",
    "dev_issuer",
    "issuer_vault",
)

FORBIDDEN_SUFFIXES = (".env", ".pem")

FORBIDDEN_CONTENT_MARKERS = (
    "STUDIO_ISSUER_PRIVATE_HEX",
    "BEGIN PRIVATE KEY",
    "wrapped_dek_plaintext",
)


def _forbidden_path(rel: str, name: str) -> str | None:
    if name in FORBIDDEN_NAMES or name.endswith(".env"):
        return f"{rel} (forbidden name)"
    low = rel.lower().replace("\\", "/")
    for sub in FORBIDDEN_NAME_SUBSTRINGS:
        if sub in low or sub in name.lower():
            return f"{rel} (forbidden private outreach/operator artifact)"
    if name.endswith(".pem"):
        return f"{rel} (forbidden suffix)"
    return None


def scan_package_dir(root: Path) -> None:
    bad: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root))
        name = path.name
        hit = _forbidden_path(rel, name)
        if hit:
            bad.append(hit)
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
