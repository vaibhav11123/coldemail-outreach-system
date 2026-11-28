"""OpenCitations — CC0 citation data as a Semantic Scholar alternative component."""

from __future__ import annotations

from typing import Any

import requests

from studio.academic.crossref import normalize_doi

BASE = "https://opencitations.net/index/api/v1"


def citations_for_doi(raw_doi: str) -> dict[str, Any]:
    """Return citing / cited DOIs for a work via OpenCitations (CC0)."""
    doi = normalize_doi(raw_doi)
    if not doi:
        return {"ok": False, "message": "Enter a DOI.", "citing": [], "cited": []}
    citing: list[str] = []
    cited: list[str] = []
    try:
        c1 = requests.get(f"{BASE}/citations/{doi}", timeout=20)
        c2 = requests.get(f"{BASE}/references/{doi}", timeout=20)
    except requests.RequestException as exc:
        return {
            "ok": False,
            "message": f"Network error: {exc}",
            "citing": [],
            "cited": [],
            "doi": doi,
        }
    if c1.status_code == 200:
        try:
            for row in c1.json():
                citing.append(row.get("citing") or row.get("cited") or "")
        except Exception:  # noqa: BLE001
            pass
    if c2.status_code == 200:
        try:
            for row in c2.json():
                cited.append(row.get("cited") or row.get("citing") or "")
        except Exception:  # noqa: BLE001
            pass
    citing = [x for x in citing if x][:25]
    cited = [x for x in cited if x][:25]
    return {
        "ok": True,
        "doi": doi,
        "citing": citing,
        "cited": cited,
        "note": (
            "Citation links from OpenCitations (CC0). "
            "This is not evidence that a professor is recruiting."
        ),
    }
