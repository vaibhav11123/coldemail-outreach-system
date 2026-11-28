"""Fail the installer build if a .env sneaks into the package."""

from __future__ import annotations

import sys
from pathlib import Path


def scan_package_dir(root: Path) -> None:
    bad = []
    for path in root.rglob("*"):
        if path.name == ".env" or path.name.endswith(".env"):
            bad.append(str(path.relative_to(root)))
    if bad:
        print("Package scan failed; forbidden env files:", ", ".join(bad), file=sys.stderr)
        raise SystemExit(1)
    print("Package scan ok")


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    scan_package_dir(root)


if __name__ == "__main__":
    main()
