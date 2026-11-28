"""Dated filesystem backups of operator control-plane state (₹0)."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from studio.paths import app_data_dir


def backup_control_plane(*, tag: str = "manual") -> dict[str, Any]:
    """Copy license_store + delivery_ledger into app_data_dir/backups/control-plane-*.

    Returns metadata describing what was copied. Missing sources are skipped.
    """
    root = app_data_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_tag = "".join(c if c.isalnum() or c in "-_" else "-" for c in tag)[:64]
    dest = root / "backups" / f"control-plane-{stamp}-{safe_tag}"
    dest.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in ("license_store.json", "delivery_ledger.sqlite", "payment_events.jsonl"):
        src = root / name
        if src.is_file():
            shutil.copy2(src, dest / name)
            copied.append(name)
    return {"dir": str(dest), "copied": copied, "tag": safe_tag}
