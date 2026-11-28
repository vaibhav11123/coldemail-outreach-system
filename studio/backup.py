"""Workspace backup / restore (SQLite + attachments + drafts zip)."""

from __future__ import annotations

import json
import shutil
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def create_backup(workspace: Path, dest_dir: Path | None = None) -> Path:
    dest_dir = dest_dir or (workspace / "backups")
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = dest_dir / f"studio-backup-{stamp}.zip"
    db_file = workspace / "studio.sqlite"
    meta = {
        "created_at": stamp,
        "format": "academic-studio-backup-v1",
        "includes": ["studio.sqlite", "attachments/", "manifest.json"],
    }
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(meta, indent=2))
        if db_file.is_file():
            # Snapshot via SQLite backup API for consistency
            snap = dest_dir / f".snap-{stamp}.sqlite"
            src = sqlite3.connect(str(db_file))
            dst = sqlite3.connect(str(snap))
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()
            zf.write(snap, arcname="studio.sqlite")
            snap.unlink(missing_ok=True)
        att = workspace / "attachments"
        if att.is_dir():
            for p in att.rglob("*"):
                if p.is_file():
                    zf.write(p, arcname=str(Path("attachments") / p.relative_to(att)))
    return out


def restore_backup(zip_path: Path, workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        db_name = "studio.sqlite" if "studio.sqlite" in names else (
            "studio.sqlite3" if "studio.sqlite3" in names else None
        )
        if db_name is None:
            raise ValueError("Backup missing studio.sqlite")
        # Replace DB
        db_file = workspace / "studio.sqlite"
        if db_file.exists():
            bak = workspace / f"studio.sqlite.pre-restore-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
            shutil.copy2(db_file, bak)
        with zf.open(db_name) as src, open(db_file, "wb") as dst:
            shutil.copyfileobj(src, dst)
        att_root = workspace / "attachments"
        for name in names:
            if not name.startswith("attachments/") or name.endswith("/"):
                continue
            target = workspace / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
