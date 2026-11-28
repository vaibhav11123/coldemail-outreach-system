"""Shared fixtures for studio tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["STUDIO_FORCE_LOCAL_SECRETS"] = "1"


@pytest.fixture()
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("STUDIO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STUDIO_FORCE_LOCAL_SECRETS", "1")
    return tmp_path


@pytest.fixture()
def client(data_dir: Path):
    # Import after env is set
    import studio.app as app_mod
    from studio.app import create_app

    application = create_app(data_dir)
    token = app_mod.PAGE_TOKEN
    with TestClient(application, base_url="http://127.0.0.1:8765") as c:
        c.cookies.set("studio_page_token", token)
        c.page_token = token  # type: ignore[attr-defined]
        yield c


@pytest.fixture()
def conn(data_dir: Path):
    from studio import db as dbmod
    from studio.demo import seed_demo
    from studio.summer_loader import seed_mini_bundled

    c = dbmod.connect(data_dir / "studio.sqlite")
    dbmod.migrate(c)
    seed_demo(c)
    seed_mini_bundled(c)
    yield c
    c.close()
