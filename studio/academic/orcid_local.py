"""ORCID public identity via CC0 annual dataset snapshot (not the paid API).

Ship a tiny fixture for tests/demo. Operators may place a larger extracted
JSONL under STUDIO_ORCID_INDEX or studio/data/orcid_public_sample.jsonl.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from studio.paths import PACKAGE_ROOT

SAMPLE_PATH = PACKAGE_ROOT / "data" / "orcid_public_sample.jsonl"


def _index_path() -> Path:
    env = os.environ.get("STUDIO_ORCID_INDEX")
    if env:
        return Path(env)
    return SAMPLE_PATH


def load_records(limit: int = 5000) -> list[dict[str, Any]]:
    path = _index_path()
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(out) >= limit:
                break
    return out


def lookup_orcid(orcid_id: str) -> dict[str, Any]:
    oid = (orcid_id or "").strip()
    if "orcid.org/" in oid:
        oid = oid.rstrip("/").split("orcid.org/")[-1]
    for rec in load_records():
        if rec.get("orcid") == oid:
            return {
                "ok": True,
                "source": "orcid_cc0_snapshot",
                "orcid": oid,
                "name": rec.get("name") or "",
                "affiliations": rec.get("affiliations") or [],
                "works": rec.get("works") or [],
                "note": "From ORCID public data (CC0). Dataset may lag real-time profiles.",
            }
    return {
        "ok": False,
        "message": (
            "ORCID not in the local CC0 snapshot. "
            "Paste the iD as a profile link, or expand the annual public dataset index."
        ),
        "orcid": oid,
    }


def search_name(query: str, limit: int = 10) -> list[dict[str, Any]]:
    q = (query or "").strip().lower()
    if not q:
        return []
    hits = []
    for rec in load_records():
        name = (rec.get("name") or "").lower()
        if q in name:
            hits.append(rec)
        if len(hits) >= limit:
            break
    return hits
