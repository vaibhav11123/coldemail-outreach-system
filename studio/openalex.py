"""OpenAlex client — student-owned key, no shared secret."""

from __future__ import annotations

import time
from typing import Any

import requests

from studio.secrets_store import get_secret, set_secret

BASE = "https://api.openalex.org"
KEY_NAME = "openalex_api_key"


def request_api_key(email: str) -> dict[str, Any]:
    """POST /api-keys — student clicks activation email."""
    resp = requests.post(
        f"{BASE}/api-keys",
        json={"email": email, "agent": "AcademicOutreachStudio"},
        headers={"Idempotency-Key": f"studio-{email}-{int(time.time() // 3600)}"},
        timeout=30,
    )
    data = {}
    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text}
    data["http_status"] = resp.status_code
    if resp.status_code == 201 and data.get("api_key"):
        set_secret(KEY_NAME, data["api_key"])
        set_secret("openalex_email", email)
        set_secret("openalex_status", data.get("status", "pending_activation"))
    return data


def save_pasted_key(key: str) -> None:
    set_secret(KEY_NAME, key.strip())
    set_secret("openalex_status", "active")


def _headers() -> dict[str, str]:
    key = get_secret(KEY_NAME)
    if key:
        return {"Authorization": f"Bearer {key}"}
    return {}


def get_works_for_author(author_id: str) -> dict[str, Any]:
    """Fetch works. Honors 429 Retry-After. Does not write on failure."""
    url = f"{BASE}/works"
    params = {"filter": f"authorships.author.id:{author_id}", "per-page": 5}
    resp = requests.get(url, params=params, headers=_headers(), timeout=30)
    if resp.status_code == 403:
        code = ""
        try:
            code = resp.json().get("error", "")
        except Exception:
            pass
        if "key_not_activated" in str(code) or "not_activated" in resp.text:
            return {
                "ok": False,
                "error": "key_not_activated",
                "message": "OpenAlex emailed an activation link. Click it, then retry.",
            }
        return {"ok": False, "error": "forbidden", "message": resp.text[:200]}
    if resp.status_code == 429:
        retry = int(resp.headers.get("Retry-After", "5"))
        return {
            "ok": False,
            "error": "rate_limited",
            "retry_after": retry,
            "message": f"OpenAlex rate limited. Wait {retry}s.",
        }
    if resp.status_code >= 400:
        return {"ok": False, "error": "http_error", "message": f"OpenAlex HTTP {resp.status_code}"}
    try:
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": "invalid_json",
            "message": f"OpenAlex returned unreadable JSON ({exc})",
        }
    if not isinstance(data, dict):
        return {"ok": False, "error": "unexpected_schema", "message": "OpenAlex payload was not an object"}
    works = []
    for w in data.get("results", []):
        title = w.get("title") or w.get("display_name") or ""
        year = w.get("publication_year")
        url = None
        primary = w.get("primary_location") or {}
        source = primary.get("source") or {}
        url = primary.get("landing_page_url") or w.get("id")
        abstract = ""
        # OpenAlex inverted index abstract optional
        inv = w.get("abstract_inverted_index") or {}
        if inv:
            # reconstruct roughly
            pairs = []
            for word, idxs in inv.items():
                for i in idxs:
                    pairs.append((i, word))
            abstract = " ".join(w for _, w in sorted(pairs))[:400]
        works.append({"title": title, "year": year, "url": url, "abstract": abstract})
    return {"ok": True, "works": works}


def authors_for_institution(institution_id: str) -> list[dict[str, str]]:
    if not institution_id:
        return []
    url = f"{BASE}/authors"
    params = {
        "filter": f"last_known_institutions.id:{institution_id}",
        "per-page": 25,
    }
    resp = requests.get(url, params=params, headers=_headers(), timeout=30)
    if resp.status_code == 429:
        raise RuntimeError(f"rate_limited:{resp.headers.get('Retry-After', '5')}")
    if resp.status_code >= 400:
        raise RuntimeError(f"OpenAlex HTTP {resp.status_code}")
    people = []
    for a in resp.json().get("results", []):
        people.append(
            {
                "name": a.get("display_name") or "",
                "email": "",
                "openalex_id": a.get("id") or "",
            }
        )
    return people
