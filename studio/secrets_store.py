"""Secret storage: OS keychain when available, encrypted-local fallback for CI."""

from __future__ import annotations

import json
import os
from pathlib import Path

from studio.paths import keychain_path

try:
    import keyring  # type: ignore
except Exception:  # pragma: no cover
    keyring = None

SERVICE = "academic-outreach-studio"


def _local_store() -> Path:
    return keychain_path()


def _read_local() -> dict:
    path = _local_store()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_local(data: dict) -> None:
    path = _local_store()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    os.chmod(path, 0o600)


def set_secret(name: str, value: str) -> None:
    if keyring is not None and os.environ.get("STUDIO_FORCE_LOCAL_SECRETS") != "1":
        try:
            keyring.set_password(SERVICE, name, value)
            return
        except Exception:
            pass
    data = _read_local()
    data[name] = value
    _write_local(data)


def get_secret(name: str) -> str | None:
    if keyring is not None and os.environ.get("STUDIO_FORCE_LOCAL_SECRETS") != "1":
        try:
            value = keyring.get_password(SERVICE, name)
            if value:
                return value
        except Exception:
            pass
    return _read_local().get(name)


def delete_secret(name: str) -> None:
    if keyring is not None and os.environ.get("STUDIO_FORCE_LOCAL_SECRETS") != "1":
        try:
            keyring.delete_password(SERVICE, name)
        except Exception:
            pass
    data = _read_local()
    if name in data:
        del data[name]
        _write_local(data)


def delete_all_studio_secrets() -> None:
    data = _read_local()
    for key in list(data):
        delete_secret(key)
    if _local_store().exists():
        _local_store().unlink()
