"""OpenCitations — CC0 citation data as a Semantic Scholar alternative component."""

from __future__ import annotations

from typing import Any

import requests

from studio.academic.crossref import normalize_doi

# Public API host (opencitations.net/index/api/v1 redirects; hit the API origin directly)
BASE = "https://api.opencitations.net/index/v1"
MAX_BYTES = 512_000  # enough for dozens of citation rows; avoid multi‑MB IncompleteRead


def _get_json(url: str) -> tuple[list | None, str | None]:
    try:
        resp = requests.get(url, timeout=30, stream=True)
    except requests.RequestException as exc:
        return None, f"Network error: {exc}"
    if resp.status_code >= 400:
        return None, f"OpenCitations HTTP {resp.status_code}"
    chunks: list[bytes] = []
    total = 0
    truncated = False
    try:
        for chunk in resp.iter_content(8192):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_BYTES:
                truncated = True
                break
            chunks.append(chunk)
    except requests.RequestException as exc:
        # Partial body still useful when the connection dies mid-transfer
        if not chunks:
            return None, f"Network error: {exc}"
        truncated = True
    finally:
        resp.close()
    raw = b"".join(chunks)
    if not raw:
        return [], None
    try:
        import json

        data = json.loads(raw.decode("utf-8", errors="replace"))
        if isinstance(data, list):
            return data, ("truncated" if truncated else None)
        return [], None
    except Exception:
        # Truncated JSON — return empty rather than failing the whole Connections panel
        return [], "truncated_response"


def citations_for_doi(raw_doi: str) -> dict[str, Any]:
    """Return citing / cited DOIs for a work via OpenCitations (CC0)."""
    doi = normalize_doi(raw_doi)
    if not doi:
        return {"ok": False, "message": "Enter a DOI.", "citing": [], "cited": []}
    citing_rows, err1 = _get_json(f"{BASE}/citations/{doi}")
    cited_rows, err2 = _get_json(f"{BASE}/references/{doi}")
    if citing_rows is None and cited_rows is None:
        return {
            "ok": False,
            "message": err1 or err2 or "OpenCitations unavailable",
            "citing": [],
            "cited": [],
            "doi": doi,
        }
    citing: list[str] = []
    cited: list[str] = []
    for row in citing_rows or []:
        if isinstance(row, dict):
            citing.append(row.get("citing") or row.get("cited") or "")
    for row in cited_rows or []:
        if isinstance(row, dict):
            cited.append(row.get("cited") or row.get("citing") or "")
    citing = [x for x in citing if x][:25]
    cited = [x for x in cited if x][:25]
    note = (
        "Citation links from OpenCitations (CC0). "
        "This is not evidence that a professor is recruiting."
    )
    if err1 == "truncated" or err2 == "truncated" or err1 == "truncated_response":
        note += " Response truncated for size; showing the first rows only."
    return {
        "ok": True,
        "doi": doi,
        "citing": citing,
        "cited": cited,
        "note": note,
    }
