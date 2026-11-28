"""Contract / failure-mode tests for academic providers (mocked)."""

from __future__ import annotations

from unittest import mock

import pytest

from studio import openalex
from studio.academic import crossref
from studio.academic.opencitations import citations_for_doi
from studio.ai.engine import rewrite_draft
from studio.ai.types import EvidenceBoundRequest


class _Resp:
    def __init__(self, status: int, payload=None, headers=None, text=""):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._payload


@pytest.mark.parametrize("status,err", [(401, None), (403, None), (404, None), (429, "rate"), (500, None), (503, None)])
def test_openalex_http_failures(status, err):
    headers = {"Retry-After": "3"} if status == 429 else {}
    with mock.patch(
        "studio.openalex.requests.get",
        return_value=_Resp(status, {}, headers, "x"),
    ):
        out = openalex.get_works_for_author("A1")
    assert out["ok"] is False


def test_openalex_invalid_json():
    class Bad(_Resp):
        def json(self):
            raise ValueError("not json")

    with mock.patch("studio.openalex.requests.get", return_value=Bad(200, text="{")):
        out = openalex.get_works_for_author("A1")
    assert out["ok"] is False


def test_crossref_timeout():
    with mock.patch(
        "studio.academic.crossref.requests.get",
        side_effect=__import__("requests").exceptions.Timeout(),
    ):
        out = crossref.lookup_doi("10.1000/xyz")
    assert out["ok"] is False


def test_opencitations_network_failure():
    with mock.patch(
        "studio.academic.opencitations.requests.get",
        side_effect=__import__("requests").exceptions.ConnectionError("down"),
    ):
        out = citations_for_doi("10.1000/xyz")
        assert out["ok"] is False
        assert out["citing"] == []


def test_INV10_ai_failure_falls_back_deterministic_not_paid_switch():
    req = EvidenceBoundRequest(
        recipient="p@ex.edu",
        subject="s",
        body='Body with "Attention patterns" https://example.edu/p/1 and Built a tokenizer for code.',
        evidence_snippets=[
            "Attention patterns",
            "https://example.edu/p/1",
            "Built a tokenizer for code",
        ],
        citations=[
            {
                "applicant": "Built a tokenizer for code",
                "source": "Attention patterns",
                "url": "https://example.edu/p/1",
            }
        ],
    )
    with mock.patch("studio.ai.engine.get_active_provider", return_value=None):
        result = rewrite_draft(req)
    assert result.ok
    assert result.used_deterministic_fallback or result.provider_id == "deterministic"
