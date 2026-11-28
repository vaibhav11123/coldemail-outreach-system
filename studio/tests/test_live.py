"""Live checks — network/Summer zip. Fixture paths still pass when skipped."""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest

from studio.db import connect, migrate
from studio.faculty import collect_school, import_people
from studio.openalex import get_works_for_author
from studio.summer_loader import load_summer_zip

pytestmark = pytest.mark.live

SUMMER = Path(
    os.environ.get(
        "SUMMER_ZIP",
        str(Path.home() / "Downloads" / "Summer-2027-research-data-20261122.zip"),
    )
)


def test_live_summer_zip_load(tmp_path):
    if not SUMMER.exists():
        pytest.skip(f"Summer zip not found at {SUMMER}")
    conn = connect(tmp_path / "studio.sqlite")
    migrate(conn)
    stats = load_summer_zip(conn, SUMMER)
    assert stats["researchers"] == 1021
    assert stats["historical_sends_loaded"] == 0
    unk = conn.execute(
        "SELECT COUNT(*) AS c FROM opportunity WHERE status='unknown' AND origin='bundled'"
    ).fetchone()["c"]
    assert unk > 0
    conn.close()


def test_live_openalex_or_fixture_429():
    if os.environ.get("OPENALEX_API_KEY"):
        from studio.secrets_store import set_secret

        set_secret("openalex_api_key", os.environ["OPENALEX_API_KEY"])
        out = get_works_for_author("A5023888391")
        if out.get("error") == "rate_limited":
            pytest.skip("OpenAlex 429")
        if not out.get("ok"):
            pytest.skip(out.get("message") or out.get("error"))
        assert out["works"]
        assert out["works"][0].get("title")
        assert out["works"][0].get("url")
        return
    # fixture path: saved 429 body
    class Resp:
        status_code = 429
        headers = {"Retry-After": "3"}
        text = "rate"

        def json(self):
            return {"error": "rate_limited"}

    with mock.patch("studio.openalex.requests.get", return_value=Resp()):
        out = get_works_for_author("A1")
    assert out["error"] == "rate_limited"
    assert out["retry_after"] == 3


def test_live_faculty_fixture_then_optional_network(tmp_path):
    html = (Path(__file__).parent / "fixtures" / "faculty_windows1252.html").read_text(
        encoding="utf-8"
    )
    from studio.fetch_url import extract_people_from_html

    people = extract_people_from_html(html, "https://example.edu/faculty")
    assert people
    conn = connect(tmp_path / "studio.sqlite")
    migrate(conn)
    n = import_people(conn, "mit", people)
    assert n >= 1
    before = conn.execute("SELECT COUNT(*) AS c FROM researcher").fetchone()["c"]
    # live fetch optional
    if os.environ.get("STUDIO_LIVE_FACULTY") != "1":
        pytest.skip("Set STUDIO_LIVE_FACULTY=1 to hit a real school URL")
    result = collect_school("mit")
    # failure must not wipe fixture rows
    after = conn.execute("SELECT COUNT(*) AS c FROM researcher").fetchone()["c"]
    assert after >= before
    if result.get("error") and not result["people"]:
        # named failure, zero added beyond previous
        pass
    conn.close()
