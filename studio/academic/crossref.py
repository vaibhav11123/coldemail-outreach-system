"""Crossref public REST — DOI / publication verification (no customer registration)."""

from __future__ import annotations

import re
from typing import Any

import requests

_DOI_RE = re.compile(r"10\.\d{4,9}/\S+", re.I)


def normalize_doi(raw: str) -> str | None:
    text = (raw or "").strip()
    if text.lower().startswith("https://doi.org/"):
        text = text.split("doi.org/", 1)[1]
    if text.lower().startswith("doi:"):
        text = text[4:].strip()
    m = _DOI_RE.search(text)
    return m.group(0).rstrip(".)]") if m else None


def lookup_doi(raw: str) -> dict[str, Any]:
    doi = normalize_doi(raw)
    if not doi:
        return {"ok": False, "message": "Enter a DOI (for example 10.1038/nature14539)."}
    url = f"https://api.crossref.org/works/{doi}"
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "AcademicOutreachStudio/1.0 (mailto:support@academic-outreach.studio)"},
            timeout=20,
        )
    except requests.RequestException as exc:
        return {"ok": False, "message": f"Network error: {exc}"}
    if resp.status_code == 404:
        return {"ok": False, "message": "DOI not found in Crossref."}
    if resp.status_code >= 400:
        return {"ok": False, "message": f"Crossref HTTP {resp.status_code}"}
    msg = resp.json().get("message") or {}
    titles = msg.get("title") or []
    title = titles[0] if titles else ""
    year = None
    issued = (msg.get("issued") or {}).get("date-parts") or []
    if issued and issued[0]:
        year = issued[0][0]
    authors = []
    for a in msg.get("author") or []:
        name = " ".join(x for x in [a.get("given"), a.get("family")] if x)
        if name:
            authors.append(name)
    return {
        "ok": True,
        "doi": doi,
        "title": title,
        "year": year,
        "authors": authors[:8],
        "url": f"https://doi.org/{doi}",
        "container": (msg.get("container-title") or [""])[0],
        "note": "Publication metadata is evidence of research activity, not of an open internship.",
    }
