"""Print Precision@5, Recall@10, and nDCG@10 for labeled pairs."""

from __future__ import annotations

import json
import math
from pathlib import Path

from studio.matching import score_opportunity

PAIRS = Path(__file__).with_name("labeled_pairs.json")


def ndcg_at_k(relevances: list[int], k: int) -> float:
    k = min(k, len(relevances))
    dcg = sum(relevances[i] / math.log2(i + 2) for i in range(k))
    ideal = sorted(relevances, reverse=True)
    idcg = sum(ideal[i] / math.log2(i + 2) for i in range(k))
    return (dcg / idcg) if idcg else 0.0


def main() -> None:
    pairs = json.loads(PAIRS.read_text(encoding="utf-8"))
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
        scored.append((score, int(p["relevant"]), p["id"], reasons))
    scored.sort(key=lambda x: x[0], reverse=True)

    top5 = scored[:5]
    precision5 = sum(r for _, r, _, _ in top5) / 5
    top10 = scored[:10]
    relevant_total = sum(1 for p in pairs if p["relevant"])
    recall10 = sum(r for _, r, _, _ in top10) / max(1, relevant_total)
    relevances = [r for _, r, _, _ in scored]
    ndcg10 = ndcg_at_k(relevances, 10)

    print(f"Precision@5: {precision5:.3f}")
    print(f"Recall@10: {recall10:.3f}")
    print(f"nDCG@10: {ndcg10:.3f}")
    failures = [s for s in scored[:10] if s[1] == 0]
    print(f"False positives in top-10: {[f[2] for f in failures]}")


if __name__ == "__main__":
    main()
