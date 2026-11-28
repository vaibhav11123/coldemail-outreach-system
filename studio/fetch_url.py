"""Safe single-URL fetch with SSRF protections."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from studio.security import is_blocked_ip, resolve_and_validate

MAX_BYTES = 1_000_000
TIMEOUT = 20


class _RedirectTracker(requests.Session):
    def __init__(self):
        super().__init__()
        self.seen_urls: list[str] = []

    def get_redirect_target(self, resp):  # type: ignore[override]
        return super().get_redirect_target(resp)


def fetch_text(url: str) -> tuple[str, str]:
    """Return (final_url, text). Raises ValueError on SSRF/size/timeout."""
    resolve_and_validate(url)
    session = requests.Session()
    session.max_redirects = 5

    def _hook(response, *args, **kwargs):
        # re-validate every hop
        resolve_and_validate(response.url)
        return response

    session.hooks["response"] = [_hook]
    headers = {"User-Agent": "AcademicOutreachStudio/0.1 (+local; research tool)"}
    resp = session.get(url, timeout=TIMEOUT, headers=headers, stream=True, allow_redirects=True)
    resolve_and_validate(resp.url)
    # size cap
    chunks = []
    total = 0
    for chunk in resp.iter_content(8192):
        total += len(chunk)
        if total > MAX_BYTES:
            raise ValueError("Response exceeds size limit")
        chunks.append(chunk)
    raw = b"".join(chunks)
    # charset
    ctype = resp.headers.get("Content-Type", "")
    m = re.search(r"charset=([\w-]+)", ctype, re.I)
    # Do not use resp.apparent_encoding after streaming — it re-reads the body
    # and raises "content already consumed".
    encoding = (m.group(1) if m else None) or "utf-8"
    for enc in (encoding, "utf-8", "windows-1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")
    return resp.url, text


def extract_opportunity_suggestions(html: str, page_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    suggestions: list[dict[str, Any]] = []

    # deadlines
    for m in re.finditer(
        r"(deadline|apply by|applications? due)[:\s]+(\d{4}-\d{2}-\d{2}|\d{1,2}\s+\w+\s+\d{4})",
        text,
        re.I,
    ):
        suggestions.append(
            {
                "field": "deadline",
                "value": m.group(2),
                "quote": m.group(0)[:200],
                "url": page_url,
            }
        )

    low = text.lower()
    if re.search(r"\binternational students? (are )?eligible\b", low):
        suggestions.append(
            {
                "field": "eligibility",
                "value": "stated-yes",
                "quote": "international students eligible",
                "url": page_url,
            }
        )
    if re.search(r"\bfunded\b", low) and "unfunded" not in low:
        suggestions.append(
            {
                "field": "funding",
                "value": "stated-yes",
                "quote": "funded",
                "url": page_url,
            }
        )
    if re.search(r"applications? (are )?open\b", low):
        suggestions.append(
            {
                "field": "status",
                "value": "stated-yes",
                "quote": "applications open",
                "url": page_url,
            }
        )

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "apply" in href.lower() or "application" in (a.get_text() or "").lower():
            full = urljoin(page_url, href)
            if urlparse(full).scheme in {"http", "https"}:
                suggestions.append(
                    {
                        "field": "apply_url",
                        "value": full,
                        "quote": a.get_text(strip=True)[:120] or full,
                        "url": page_url,
                    }
                )
                break
    return suggestions


def extract_people_from_html(html: str, page_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    people = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href.lower().startswith("mailto:"):
            # obfuscated
            continue
        email = href.split(":", 1)[1].split("?")[0].strip()
        email = email.replace("%40", "@")
        if not email or email in seen:
            continue
        seen.add(email)
        name = a.get_text(strip=True)
        if not name or "@" in name:
            # look at parent text
            parent = a.parent.get_text(" ", strip=True) if a.parent else ""
            name = re.sub(re.escape(email), "", parent).strip(" -<>,;")[:120] or email.split("@")[0]
        people.append({"name": name, "email": email, "source_url": page_url})
    # obfuscated patterns
    text = soup.get_text(" ", strip=True)
    for m in re.finditer(r"([A-Za-z0-9._%+-]+)\s*\[\s*at\s*\]\s*([A-Za-z0-9.-]+)", text):
        email = f"{m.group(1)}@{m.group(2)}"
        if email not in seen:
            seen.add(email)
            people.append({"name": m.group(1), "email": email, "source_url": page_url})
    return people
