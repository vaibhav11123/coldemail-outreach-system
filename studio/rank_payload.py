"""Normalize shortlist rank_explanation JSON (legacy list vs intel payload)."""

from __future__ import annotations

import json
from typing import Any


def parse_rank_explanation(raw: str | None) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    if not raw:
        return [], None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return [], None
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        reasons = data.get("reasons") or []
        intel = data.get("intel")
        if not isinstance(reasons, list):
            reasons = []
        return reasons, intel if isinstance(intel, dict) else None
    return [], None
