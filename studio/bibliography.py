"""Bibliography imports — BibTeX / RIS / CSV (Google Scholar export, Zotero files)."""

from __future__ import annotations

import csv
import io
import re
from typing import Any

_BIB_ENTRY = re.compile(r"@\w+\s*\{([^,]+),", re.I)
_BIB_FIELD = re.compile(r"(\w+)\s*=\s*[{\"]([^}\"]+)[}\"]", re.I)


def parse_bibliography(text: str, filename: str = "") -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {"ok": False, "message": "Empty file.", "entries": []}
    lower = (filename or "").lower()
    first = next((ln.strip() for ln in raw.splitlines() if ln.strip()), "")
    if lower.endswith(".ris") or first.startswith("TY  -"):
        entries = _parse_ris(raw)
        kind = "ris"
    elif lower.endswith((".bib", ".bibtex")) or first.startswith("@"):
        entries = _parse_bibtex(raw)
        kind = "bibtex"
    elif lower.endswith(".csv") or (
        "," in first and "title" in first.lower() and not first.startswith("@")
    ):
        entries = _parse_csv(raw)
        kind = "csv"
    else:
        entries = _parse_bibtex(raw)
        kind = "bibtex"
    if not entries:
        return {
            "ok": False,
            "message": "No publications found. Export BibTeX, RIS, or CSV from Scholar/Zotero.",
            "entries": [],
        }
    return {"ok": True, "kind": kind, "entries": entries, "count": len(entries)}


def _parse_bibtex(raw: str) -> list[dict[str, str]]:
    entries = []
    chunks = re.split(r"(?=@\w+\s*\{)", raw)
    for chunk in chunks:
        if not chunk.strip().startswith("@"):
            continue
        fields = {k.lower(): v.strip() for k, v in _BIB_FIELD.findall(chunk)}
        title = fields.get("title") or ""
        if not title:
            continue
        year = fields.get("year") or ""
        doi = fields.get("doi") or ""
        author = fields.get("author") or ""
        url = f"https://doi.org/{doi}" if doi else fields.get("url") or ""
        entries.append(
            {
                "title": title,
                "year": year,
                "authors": author.replace(" and ", "; "),
                "doi": doi,
                "url": url,
                "suggested_body": f"{title}"
                + (f" ({year})" if year else "")
                + (f" — {author.split(' and ')[0]}" if author else "")
                + (f" {url}" if url else ""),
            }
        )
    return entries


def _parse_ris(raw: str) -> list[dict[str, str]]:
    entries = []
    current: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.startswith("TY  -"):
            if current.get("title"):
                entries.append(_ris_entry(current))
            current = {}
            continue
        if line.startswith("ER  -"):
            if current.get("title"):
                entries.append(_ris_entry(current))
            current = {}
            continue
        if "  - " in line[:6]:
            tag, _, val = line.partition("  - ")
            tag = tag.strip()
            val = val.strip()
            if tag == "TI":
                current["title"] = val
            elif tag == "PY":
                current["year"] = val[:4]
            elif tag == "AU":
                current["authors"] = (
                    (current.get("authors") + "; " + val) if current.get("authors") else val
                )
            elif tag == "DO":
                current["doi"] = val
            elif tag == "UR":
                current["url"] = val
    if current.get("title"):
        entries.append(_ris_entry(current))
    return entries


def _ris_entry(current: dict[str, str]) -> dict[str, str]:
    title = current.get("title") or ""
    year = current.get("year") or ""
    doi = current.get("doi") or ""
    url = current.get("url") or (f"https://doi.org/{doi}" if doi else "")
    authors = current.get("authors") or ""
    return {
        "title": title,
        "year": year,
        "authors": authors,
        "doi": doi,
        "url": url,
        "suggested_body": f"{title}"
        + (f" ({year})" if year else "")
        + (f" {url}" if url else ""),
    }


def _parse_csv(raw: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(raw))
    entries = []
    for row in reader:
        lower = { (k or "").lower().strip(): (v or "").strip() for k, v in row.items() }
        title = lower.get("title") or lower.get("article title") or ""
        if not title:
            continue
        year = lower.get("year") or lower.get("publication year") or ""
        authors = lower.get("authors") or lower.get("author") or ""
        doi = lower.get("doi") or ""
        url = lower.get("url") or (f"https://doi.org/{doi}" if doi else "")
        entries.append(
            {
                "title": title,
                "year": year,
                "authors": authors,
                "doi": doi,
                "url": url,
                "suggested_body": f"{title}"
                + (f" ({year})" if year else "")
                + (f" {url}" if url else ""),
            }
        )
    return entries


def import_entries_as_facts(conn, entries: list[dict[str, str]], source: str = "bibliography") -> int:
    n = 0
    for e in entries:
        body = e.get("suggested_body") or e.get("title") or ""
        if not body:
            continue
        existing = conn.execute(
            "SELECT id FROM profile_fact WHERE kind='paper' AND body=?",
            (body,),
        ).fetchone()
        if existing:
            continue
        conn.execute(
            """
            INSERT INTO profile_fact(applicant_id, kind, body, source, confirmed)
            VALUES (1, 'paper', ?, ?, 0)
            """,
            (body, source),
        )
        n += 1
    return n
