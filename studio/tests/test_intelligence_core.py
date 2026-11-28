"""Faculty discovery, CV import, match intel, evidence-grounded drafting."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("STUDIO_FORCE_BOW_EMBEDDINGS", "1")
os.environ.setdefault("STUDIO_FORCE_LOCAL_SECRETS", "1")

from studio.cv_import import parse_cv, persist_extracted_profile, structure_cv_text
from studio.drafting.composer import compose_application
from studio.drafting.quality import inspect_application_quality
from studio.drafting.evidence import build_evidence_graph
from studio.drafting.schemas import WritingPreferences
from studio.match_intel import explain_match
from studio.matching import rebuild_shortlist
from studio.rank_payload import parse_rank_explanation
from studio.search.hybrid import ensure_search_indexes, hybrid_search_researchers
from studio.search.fts import search_faculty_fts


def test_cv_text_extraction_and_structure():
    sample = """
    Jane Student
    Interests: GPU systems and distributed training
    Skills: Python, CUDA, PyTorch
    Projects
    Built a fused MoE kernel and benchmarked throughput on A100 GPUs.
    Coursework: Operating Systems, Compilers
    https://github.com/jane/moe-kernel
    """
    profile = structure_cv_text(sample)
    assert profile.skills
    assert any("CUDA" in s or "cuda" in s.lower() or "Python" in s for s in profile.skills)
    assert profile.urls


def test_cv_pdf_roundtrip_bytes():
    # Minimal valid-enough path: plain text disguised — parse_cv handles txt
    data = b"Skills: Rust, Linux\nInterests: systems research for ML\n"
    result = parse_cv("cv.txt", data)
    assert result.source_format == "txt"
    assert result.profile.interests or result.profile.skills


def test_fts_and_hybrid_directory(conn):
    ensure_search_indexes(conn)
    hits = search_faculty_fts(conn, "kernel scheduling", limit=10)
    assert hits
    hybrid = hybrid_search_researchers(conn, "mixture experts inference", limit=10)
    assert hybrid
    assert hybrid[0]["display_name"]


def test_match_intel_not_acceptance_probability(conn):
    conn.execute(
        "INSERT INTO profile_fact(kind, body, source, confirmed) VALUES ('interest', 'GPU kernel optimization for MoE', 'typed', 1)"
    )
    conn.execute(
        "INSERT INTO profile_fact(kind, body, source, confirmed) VALUES ('skill', 'CUDA', 'typed', 1)"
    )
    conn.execute(
        "INSERT INTO profile_fact(kind, body, source, confirmed) VALUES ('project', 'Fused expert kernel benchmark', 'typed', 1)"
    )
    opp = dict(conn.execute("SELECT * FROM opportunity LIMIT 1").fetchone())
    pubs = [
        dict(p)
        for p in conn.execute(
            "SELECT title, year, url, abstract FROM publication WHERE researcher_id=?",
            (opp["researcher_id"],),
        )
    ]
    facts = [
        dict(r)
        for r in conn.execute(
            "SELECT kind, body, confirmed FROM profile_fact WHERE confirmed=1"
        )
    ]
    intel = explain_match(facts, opp, pubs)
    assert "acceptance" in intel.disclaimer.lower() or "not an acceptance" in intel.disclaimer.lower()
    assert 0 <= intel.overall <= 100
    rebuild_shortlist(conn)
    raw = conn.execute(
        "SELECT rank_explanation FROM shortlist_item WHERE opportunity_id=?",
        (opp["id"],),
    ).fetchone()["rank_explanation"]
    reasons, payload = parse_rank_explanation(raw)
    assert payload is not None
    assert "overall" in payload


def test_learning_oriented_draft_without_project():
    facts = [
        {"kind": "interest", "body": "efficient machine learning systems", "confirmed": 1},
        {"kind": "coursework", "body": "Operating Systems and Parallel Computing", "confirmed": 1},
        {"kind": "skill", "body": "Python", "confirmed": 1},
    ]
    pubs = [
        {
            "title": "Kernel scheduling for mixture-of-experts inference",
            "url": "https://example.edu/papers/ada-1",
            "abstract": "We study expert scheduling to reduce inference overhead on accelerators.",
        }
    ]
    draft = compose_application(
        researcher_name="Ada Example",
        recipient="ada.example@uni.edu",
        profile_facts=facts,
        publications=pubs,
        reasons=[],
        prefs=WritingPreferences(intent="summer_internship"),
        use_ai=False,
    )
    assert "Dear" in draft["body"]
    assert draft["strategy"] in {
        "learning_oriented",
        "research_alignment",
        "technical_contribution",
        "publication_led",
    }
    graph = build_evidence_graph(facts, pubs, [])
    report = inspect_application_quality(
        subject=draft["subject"],
        body=draft["body"],
        researcher_name="Ada Example",
        institution="Example University",
        evidence=graph,
        opportunity={"status": "unknown", "funding": "unknown"},
    )
    assert report.checks
    assert any(c.id == "funding" for c in report.checks)


def test_directory_route(client, conn):
    # client uses its own DB; seed via create_app already has mini bundle
    r = client.get("/directory?q=kernel")
    assert r.status_code == 200
    assert b"Faculty directory" in r.content or b"directory" in r.content.lower()


def test_persist_cv_facts(conn):
    profile = structure_cv_text(
        "Interests: compilers\nSkills: Rust\nProjects\nWrote a toy register allocator.\n"
    )
    n = persist_extracted_profile(conn, profile, confirmed=False)
    assert n >= 1
    unconfirmed = conn.execute(
        "SELECT COUNT(*) AS c FROM profile_fact WHERE source='cv' AND confirmed=0"
    ).fetchone()["c"]
    assert unconfirmed >= 1
