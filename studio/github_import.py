"""Import public GitHub repositories as unconfirmed profile projects."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import requests

from studio.secrets_store import delete_secret, get_secret, set_secret

GITHUB_LOGIN_SECRET = "github_login"
_USER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")


def parse_github_login(raw: str) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None
    if text.startswith("http://") or text.startswith("https://"):
        path = urlparse(text).path.strip("/")
        login = path.split("/")[0] if path else ""
    else:
        login = text.lstrip("@").split("/")[0]
    if not login or not _USER_RE.match(login):
        return None
    return login


def fetch_public_repos(login: str, *, per_page: int = 10) -> dict[str, Any]:
    url = f"https://api.github.com/users/{login}/repos"
    try:
        resp = requests.get(
            url,
            params={
                "type": "owner",
                "sort": "updated",
                "per_page": per_page,
            },
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "AcademicOutreachStudio",
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        return {"ok": False, "message": f"Network error: {exc}", "repos": []}
    if resp.status_code == 404:
        return {"ok": False, "message": "GitHub user not found.", "repos": []}
    if resp.status_code == 403:
        return {
            "ok": False,
            "message": "GitHub rate limited. Try again later or wait for the public limit to reset.",
            "repos": [],
        }
    if resp.status_code >= 400:
        return {"ok": False, "message": f"GitHub HTTP {resp.status_code}", "repos": []}
    repos = []
    for item in resp.json():
        if item.get("fork"):
            continue
        if item.get("private"):
            continue
        topics = item.get("topics") or []
        lang = item.get("language") or "Project"
        desc = (item.get("description") or "").strip()
        name = item.get("name") or "repo"
        label_bits = [lang] + topics[:2]
        repos.append(
            {
                "name": name,
                "url": item.get("html_url") or "",
                "description": desc,
                "language": lang,
                "topics": topics,
                "suggested_body": (
                    f"{name}"
                    + (f" — {desc}" if desc else "")
                    + f" ({', '.join(label_bits)})"
                    + (f" {item.get('html_url')}" if item.get("html_url") else "")
                ),
            }
        )
    return {"ok": True, "repos": repos, "login": login}


def import_repos_as_facts(conn, login: str, repos: list[dict[str, Any]]) -> int:
    """Insert unconfirmed project facts for student review (CON: confirm before use)."""
    n = 0
    for repo in repos:
        body = repo.get("suggested_body") or repo.get("name") or ""
        if not body:
            continue
        existing = conn.execute(
            "SELECT id FROM profile_fact WHERE kind='project' AND body=?",
            (body,),
        ).fetchone()
        if existing:
            continue
        conn.execute(
            """
            INSERT INTO profile_fact(applicant_id, kind, body, source, confirmed)
            VALUES (1, 'project', ?, 'github', 0)
            """,
            (body,),
        )
        n += 1
    set_secret(GITHUB_LOGIN_SECRET, login)
    return n


def disconnect_github() -> None:
    delete_secret(GITHUB_LOGIN_SECRET)


def github_login() -> str:
    return get_secret(GITHUB_LOGIN_SECRET) or ""
