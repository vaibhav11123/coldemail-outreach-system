"""Application data paths."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent


def app_data_dir() -> Path:
    override = os.environ.get("STUDIO_DATA_DIR")
    if override:
        path = Path(override)
    else:
        path = Path.home() / ".academic-outreach-studio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return app_data_dir() / "studio.sqlite"


def keychain_path() -> Path:
    """Local secret store used when OS keychain is unavailable in tests/CI."""
    return app_data_dir() / "secrets.json"


def bundled_data_dir() -> Path:
    return PACKAGE_ROOT / "data" / "bundled"


def demo_data_dir() -> Path:
    return PACKAGE_ROOT / "data" / "demo"
