"""Ten-pair draft quality check vs generic template."""

from __future__ import annotations

import json
from pathlib import Path

from studio.drafts import generate_draft

PAIRS = Path(__file__).resolve().parents[1] / "benchmarks" / "labeled_pairs.json"
RESULT = Path(__file__).resolve().parents[1] / "benchmarks" / "draft_blind_check.json"


def test_ten_pair_draft_beats_generic():
    pairs = [p for p in json.loads(PAIRS.read_text()) if p["relevant"]][:10]
    results = []
    wins = 0
    for p in pairs:
        facts = [
            {"kind": "project", "body": p["applicant_project"], "confirmed": 1},
        ]
        pubs = [
            {
                "title": p["lab_title"],
                "abstract": p["lab_abstract"],
                "url": f"https://example.edu/papers/{p['id']}",
                "year": 2024,
            }
        ]
        draft = generate_draft("Professor Example", "p@ex.edu", facts, pubs, [])
        generic = f"I read your paper on {p['lab_title']}"
        # win if draft grounds student evidence + faculty theme without a generic opener.
        # URLs stay on the evidence/citation record — not forced into recipient-facing prose.
        project_tokens = set(p["applicant_project"].lower().split())
        specific = any(
            t in draft["body"].lower()
            for t in project_tokens
            if len(t) > 5 and t not in {"built", "implemented", "designed", "trained"}
        )
        cites_lab = any(
            t in (draft["body"] + draft["subject"]).lower()
            for t in p["lab_title"].lower().split()
            if len(t) > 5
        ) or any((c.get("url") or "") == pubs[0]["url"] for c in draft.get("citations") or [])
        win = specific and cites_lab and generic.lower() not in draft["body"].lower()
        if win:
            wins += 1
        results.append(
            {
                "id": p["id"],
                "win": win,
                "subject": draft["subject"],
                "cites_lab": cites_lab,
                "specific": specific,
                "strategy": draft.get("strategy"),
            }
        )
    RESULT.write_text(json.dumps({"wins": wins, "results": results}, indent=2), encoding="utf-8")
    assert wins >= 7
