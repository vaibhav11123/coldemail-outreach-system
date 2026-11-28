"""Regression tests for run-2 security hardening (ZipSlip, SSRF, path confinement)."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest

from studio.ai.providers.custom import CustomProvider
from studio.dataset.forensic import inspect_path


@pytest.fixture()
def local_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("STUDIO_FORCE_LOCAL_SECRETS", "1")
    return tmp_path


def test_forensic_skips_zipslip_members(tmp_path):
    zpath = tmp_path / "evil.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("../../escape.txt", b"pwned")
        zf.writestr("safe.csv", b"export_id\nR-ABCDEF12\n")
    report = inspect_path(zpath)
    assert not (tmp_path / "escape.txt").exists()
    assert any("Skipped unsafe" in n for n in report.notes)
    assert "R-ABCDEF12" in report.matched_export_ids


def test_custom_ai_blocks_loopback_base_url(local_secrets):
    result = CustomProvider().connect_finish(base_url="http://127.0.0.1:9")
    assert result.ok is False
    assert "Blocked" in (result.message or "")


def test_custom_ai_blocks_metadata_ip(local_secrets, monkeypatch):
    # Force DNS to return link-local metadata IP
    import studio.security as sec

    def fake_getaddrinfo(host, port):
        return [(None, None, None, None, ("169.254.169.254", 0))]

    monkeypatch.setattr(sec.socket, "getaddrinfo", fake_getaddrinfo)
    result = CustomProvider().connect_finish(base_url="http://metadata.example/latest")
    assert result.ok is False
