"""Payment lifecycle helpers — durable event log + refund/revoke linkage.

Real money still moves through an approved marketplace/merchant. This module
records verified payment events locally so operators can reconcile fulfil /
refund / chargeback without a paid SaaS.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from studio.licensing.service import payment_events_path


def append_payment_event(event: dict[str, Any], path: Path | None = None) -> Path:
    out = path or payment_events_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    row = dict(event)
    row.setdefault("ts", int(time.time()))
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    return out


def iter_payment_events(path: Path | None = None) -> list[dict[str, Any]]:
    out = path or payment_events_path()
    if not out.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in out.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def record_refund(
    *,
    license_id: str,
    external_payment_id: str | None,
    reason: str,
    path: Path | None = None,
) -> Path:
    return append_payment_event(
        {
            "event": "refund_recorded",
            "license_id": license_id,
            "external_payment_id": external_payment_id,
            "reason": reason[:500],
        },
        path=path,
    )
