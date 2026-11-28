"""Hybrid BM25 + semantic search fused with Reciprocal Rank Fusion."""

from __future__ import annotations

import sqlite3
from typing import Any

from studio.search.embeddings import rebuild_faculty_embeddings, semantic_search
from studio.search.fts import rebuild_faculty_fts, search_faculty_fts

RRF_K = 60


def rrf_fuse(
    ranked_lists: list[list[int]],
    *,
    k: int = RRF_K,
) -> list[tuple[int, float]]:
    scores: dict[int, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def ensure_search_indexes(conn: sqlite3.Connection) -> dict:
    fts_n = rebuild_faculty_fts(conn)
    emb = rebuild_faculty_embeddings(conn)
    return {"fts": fts_n, **emb}


def hybrid_search_researchers(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 50,
    funding: str | None = None,
    status: str | None = None,
    university: str | None = None,
) -> list[dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        # Browse mode: structured filters only
        return _browse(conn, limit=limit, funding=funding, status=status, university=university)

    fts_hits = search_faculty_fts(conn, q, limit=limit * 2)
    fts_ids = [int(h["researcher_id"]) for h in fts_hits]
    sem_hits = semantic_search(conn, q, limit=limit * 2)
    sem_ids = [rid for rid, _ in sem_hits]
    fused = rrf_fuse([fts_ids, sem_ids])
    fts_snip = {int(h["researcher_id"]): h for h in fts_hits}
    sem_score = {rid: score for rid, score in sem_hits}

    results: list[dict[str, Any]] = []
    for rid, rrf in fused[: limit * 3]:
        detail = _researcher_card(conn, rid)
        if not detail:
            continue
        if funding and (detail.get("funding") or "") != funding:
            continue
        if status and (detail.get("status") or "") != status:
            continue
        if university and university.lower() not in (detail.get("institution") or "").lower():
            continue
        snip = fts_snip.get(rid, {})
        detail["rrf_score"] = rrf
        detail["semantic_score"] = sem_score.get(rid)
        detail["bm25"] = snip.get("bm25")
        detail["snippet"] = snip.get("paper_snip") or snip.get("name_snip") or ""
        detail["retrieval"] = "hybrid"
        results.append(detail)
        if len(results) >= limit:
            break
    return results


def _browse(
    conn: sqlite3.Connection,
    *,
    limit: int,
    funding: str | None,
    status: str | None,
    university: str | None,
) -> list[dict[str, Any]]:
    clauses = ["1=1"]
    params: list[Any] = []
    if funding:
        clauses.append("o.funding = ?")
        params.append(funding)
    if status:
        clauses.append("o.status = ?")
        params.append(status)
    if university:
        clauses.append("a.institution LIKE ?")
        params.append(f"%{university}%")
    params.append(int(limit))
    rows = conn.execute(
        f"""
        SELECT r.id AS researcher_id, r.display_name, r.email,
               a.institution, o.id AS opportunity_id, o.funding, o.status, o.note,
               o.eligibility, o.deadline
        FROM researcher r
        LEFT JOIN affiliation a ON a.researcher_id = r.id AND a.is_current = 1
        LEFT JOIN opportunity o ON o.researcher_id = r.id
        WHERE {' AND '.join(clauses)}
        ORDER BY r.display_name
        LIMIT ?
        """,
        params,
    ).fetchall()
    out = []
    for row in rows:
        d = dict(row)
        d["rrf_score"] = None
        d["retrieval"] = "browse"
        out.append(d)
    return out


def _researcher_card(conn: sqlite3.Connection, researcher_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT r.id AS researcher_id, r.display_name, r.email,
               a.institution,
               o.id AS opportunity_id, o.funding, o.status, o.note,
               o.eligibility, o.deadline,
               (SELECT p.title FROM publication p WHERE p.researcher_id=r.id
                ORDER BY p.year DESC, p.id DESC LIMIT 1) AS paper_title,
               (SELECT p.year FROM publication p WHERE p.researcher_id=r.id
                ORDER BY p.year DESC, p.id DESC LIMIT 1) AS paper_year
        FROM researcher r
        LEFT JOIN affiliation a ON a.researcher_id = r.id AND a.is_current = 1
        LEFT JOIN opportunity o ON o.researcher_id = r.id
        WHERE r.id = ?
        LIMIT 1
        """,
        (researcher_id,),
    ).fetchone()
    return dict(row) if row else None
