"""Matching metrics on labeled pairs."""

from __future__ import annotations

import json
from pathlib import Path

from studio.benchmarks.run_metrics import main, ndcg_at_k
from studio.matching import score_opportunity

PAIRS = Path(__file__).resolve().parents[1] / "benchmarks" / "labeled_pairs.json"


def test_matching_metrics_thresholds():
    pairs = json.loads(PAIRS.read_text(encoding="utf-8"))
    assert len(pairs) >= 30
    scored = []
    for p in pairs:
        facts = [
            {"kind": "project", "body": p["applicant_project"], "confirmed": 1},
            {"kind": "skill", "body": p["applicant_skills"], "confirmed": 1},
        ]
        pubs = [
            {
                "title": p["lab_title"],
                "abstract": p["lab_abstract"],
                "url": f"https://example.edu/papers/{p['id']}",
                "year": 2024,
            }
        ]
        score, reasons = score_opportunity(facts, {"note": ""}, pubs)
        for r in reasons:
            assert r.get("source")
            if r["type"] != "activity":
                assert r.get("url") or r.get("source")
        scored.append((score, int(p["relevant"])))
    scored.sort(key=lambda x: x[0], reverse=True)
    precision5 = sum(r for _, r in scored[:5]) / 5
    relevant_total = sum(1 for _, r in scored if r)
    recall10 = sum(r for _, r in scored[:10]) / max(1, relevant_total)
    ndcg10 = ndcg_at_k([r for _, r in scored], 10)
    assert precision5 >= 0.4
    assert recall10 >= 0.2
    assert ndcg10 >= 0.4


def test_run_metrics_prints(capsys):
    main()
    out = capsys.readouterr().out
    assert "Precision@5" in out
    assert "Recall@10" in out
    assert "nDCG@10" in out
