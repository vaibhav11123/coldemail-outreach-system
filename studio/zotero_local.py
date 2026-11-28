"""Zotero local API — no cloud OAuth required for desktop libraries."""

from __future__ import annotations

from typing import Any

import requests

# Default local API port documented by Zotero
LOCAL_BASE = "http://127.0.0.1:23119/api"


def detect_zotero() -> dict[str, Any]:
    try:
        resp = requests.get(f"{LOCAL_BASE}/users/0/collections", timeout=2)
    except requests.RequestException:
        return {
            "ok": False,
            "connected": False,
            "message": "Zotero not detected on this computer. Open Zotero, or import a BibTeX/RIS export instead.",
            "collections": [],
        }
    if resp.status_code >= 400:
        return {
            "ok": False,
            "connected": False,
            "message": (
                "Zotero responded but local API access was refused. "
                "Enable local API in Zotero preferences if prompted."
            ),
            "collections": [],
        }
    collections = []
    try:
        data = resp.json()
        for item in data if isinstance(data, list) else []:
            data_obj = item.get("data") or item
            collections.append(
                {
                    "key": data_obj.get("key") or item.get("key") or "",
                    "name": data_obj.get("name") or "Collection",
                }
            )
    except Exception:  # noqa: BLE001
        collections = []
    return {
        "ok": True,
        "connected": True,
        "message": f"Zotero local API available ({len(collections)} collections).",
        "collections": collections[:40],
    }
