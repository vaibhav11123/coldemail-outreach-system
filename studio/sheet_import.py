"""Ordinary CSV/Excel import with size and formula protections."""

from __future__ import annotations

import csv
import io
import re
from typing import Any

MAX_UPLOAD_BYTES = 20 * 1024 * 1024

FORMULA_PREFIXES = ("=", "+", "-", "@")


def neutralize_formula(value: str) -> str:
    text = str(value) if value is not None else ""
    if text.startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


def read_tabular(filename: str, raw: bytes) -> tuple[list[str], list[dict[str, str]], list[str]]:
    """Return headers, rows, warnings."""
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("File exceeds 20 MB limit")
    warnings: list[str] = []
    name = filename.lower()
    if name.endswith((".xlsx", ".xlsm")):
        # size of decompressed workbook roughly bounded by openpyxl read
        from openpyxl import load_workbook

        bio = io.BytesIO(raw)
        try:
            wb = load_workbook(bio, read_only=True, data_only=False)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Corrupt workbook: {exc}") from exc
        # skip hidden sheets
        visible = [s for s in wb.sheetnames if wb[s].sheet_state == "visible"]
        hidden = [s for s in wb.sheetnames if s not in visible]
        if hidden:
            warnings.append(f"Skipped hidden sheets: {', '.join(hidden)}")
        if not visible:
            raise ValueError("No visible sheets")
        ws = wb[visible[0]]
        rows_iter = ws.iter_rows(values_only=True)
        try:
            header_row = next(rows_iter)
        except StopIteration as exc:
            raise ValueError("Empty sheet") from exc
        headers = [str(h or f"column_{i}").strip() for i, h in enumerate(header_row)]
        # duplicate headers
        seen = {}
        dupes = []
        for h in headers:
            seen[h] = seen.get(h, 0) + 1
            if seen[h] > 1:
                dupes.append(h)
        if dupes:
            warnings.append(f"Duplicate columns require manual mapping: {', '.join(sorted(set(dupes)))}")
        rows = []
        for row in rows_iter:
            item = {}
            for h, v in zip(headers, row):
                item[h] = neutralize_formula("" if v is None else str(v))
            if any(item.values()):
                rows.append(item)
        return headers, rows, warnings

    # CSV
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("windows-1252")
            warnings.append("Decoded as windows-1252")
        except UnicodeDecodeError as exc:
            raise ValueError("Unknown encoding") from exc
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("Missing header row")
    headers = list(reader.fieldnames)
    # duplicates
    if len(headers) != len(set(headers)):
        warnings.append("Duplicate columns require manual mapping")
    rows = []
    for row in reader:
        item = {k: neutralize_formula(v or "") for k, v in row.items() if k is not None}
        rows.append(item)
    return headers, rows, warnings


def suggest_mapping(headers: list[str]) -> dict[str, str | None]:
    mapping = {"name": None, "affiliation": None, "email": None, "profile_url": None}
    for h in headers:
        low = h.lower()
        if mapping["name"] is None and any(x in low for x in ("name", "professor", "faculty")):
            mapping["name"] = h
        if mapping["affiliation"] is None and any(
            x in low for x in ("university", "affiliation", "institution", "school", "college")
        ):
            mapping["affiliation"] = h
        if mapping["email"] is None and "mail" in low:
            mapping["email"] = h
        if mapping["profile_url"] is None and any(x in low for x in ("url", "profile", "homepage")):
            mapping["profile_url"] = h
    return mapping


def commit_import(conn, rows: list[dict[str, str]], mapping: dict[str, str]) -> int:
    """Atomic import. Name + university enough. Email may be blank."""
    name_col = mapping.get("name")
    aff_col = mapping.get("affiliation")
    email_col = mapping.get("email")
    if not name_col or not aff_col:
        raise ValueError("Name and university mapping required")
    count = 0
    conn.execute("BEGIN IMMEDIATE")
    try:
        for row in rows:
            name = (row.get(name_col) or "").strip()
            aff = (row.get(aff_col) or "").strip()
            email = (row.get(email_col) or "").strip() if email_col else ""
            if not name or not aff:
                continue
            # date validation example: if a date-like column is invalid, skip with note — handled upstream
            cur = conn.execute(
                """
                INSERT INTO researcher(display_name, email, origin, stale)
                VALUES (?, ?, 'import', 0)
                """,
                (name, email or None),
            )
            rid = cur.lastrowid
            ext = email.lower() if email else f"import:{name}|{aff}".lower()
            conn.execute(
                "INSERT OR IGNORE INTO researcher_id(researcher_id, source, external_id) VALUES (?, 'manual', ?)",
                (rid, ext),
            )
            conn.execute(
                "INSERT INTO affiliation(researcher_id, institution, is_current) VALUES (?, ?, 1)",
                (rid, aff),
            )
            conn.execute(
                """
                INSERT INTO opportunity(
                    researcher_id, kind, status, funding, eligibility,
                    deadline, apply_url, email_invited, checked_at, origin, demo, note
                ) VALUES (?, 'unknown', 'unknown', 'unknown', 'unknown',
                          NULL, NULL, 'unknown', date('now'), 'import', 0, 'Imported from spreadsheet')
                """,
                (rid,),
            )
            count += 1
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    return count
