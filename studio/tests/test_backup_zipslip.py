"""Backup restore must reject ZipSlip members."""

from __future__ import annotations

import io
import sqlite3
import zipfile
from pathlib import Path

import pytest

from studio.backup import restore_backup


def test_restore_rejects_parent_traversal(tmp_path: Path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    # Minimal valid DB in zip plus a malicious attachment path
    db = tmp_path / "studio.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE t(x)")
    conn.commit()
    conn.close()

    zpath = tmp_path / "evil.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.write(db, arcname="studio.sqlite")
        zf.writestr("attachments/../../evil.txt", b"pwned")

    with pytest.raises(ValueError, match="Unsafe"):
        restore_backup(zpath, workspace)

    assert not (tmp_path / "evil.txt").exists()
