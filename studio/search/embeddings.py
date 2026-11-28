"""Local embeddings for faculty catalog. FastEmbed when available; BoW fallback.

Precompute faculty vectors at index time. Customers only embed the query locally.
No remote vector DB — 1,021 rows fit in NumPy cosine search.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import sqlite3
import struct
from collections import Counter
from typing import Iterable

import numpy as np

_MODEL = None
_MODEL_FAILED = False

STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with", "by",
    "from", "is", "are", "as", "at", "this", "that", "we", "our", "their",
}


def _tokenize(text: str) -> list[str]:
    return [
        t
        for t in re.findall(r"[a-z0-9]+", (text or "").lower())
        if t not in STOP and len(t) > 2
    ]


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _bow_vector(text: str, dim: int = 256) -> np.ndarray:
    """Deterministic hashing trick BoW — offline, no model download."""
    vec = np.zeros(dim, dtype=np.float32)
    for tok in _tokenize(text):
        h = int(hashlib.md5(tok.encode()).hexdigest()[:8], 16)
        idx = h % dim
        sign = 1.0 if (h & 1) else -1.0
        vec[idx] += sign
    n = float(np.linalg.norm(vec))
    if n:
        vec /= n
    return vec


def use_fastembed() -> bool:
    if os.environ.get("STUDIO_USE_FASTEMBED", "").strip() in {"0", "false", "no"}:
        return False
    if os.environ.get("STUDIO_FORCE_BOW_EMBEDDINGS") == "1":
        return False
    return True


def _get_fastembed():
    global _MODEL, _MODEL_FAILED
    if _MODEL_FAILED or not use_fastembed():
        return None
    if _MODEL is not None:
        return _MODEL
    try:
        from fastembed import TextEmbedding

        # Small CPU ONNX model; first call may download once then stay offline.
        _MODEL = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
        return _MODEL
    except Exception:
        _MODEL_FAILED = True
        return None


def embed_texts(texts: list[str]) -> tuple[np.ndarray, str]:
    """Return (N, D) matrix and backend name ('fastembed' | 'bow')."""
    if not texts:
        return np.zeros((0, 256), dtype=np.float32), "bow"
    model = _get_fastembed()
    if model is not None:
        try:
            vectors = np.array(list(model.embed(texts)), dtype=np.float32)
            # L2 normalize
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            vectors = vectors / np.where(norms == 0, 1, norms)
            return vectors, "fastembed"
        except Exception:
            pass
    mat = np.stack([_bow_vector(t) for t in texts])
    return mat, "bow"


def pack_vector(vec: np.ndarray) -> bytes:
    flat = np.asarray(vec, dtype=np.float32).ravel()
    return struct.pack(f"I{len(flat)}f", len(flat), *flat.tolist())


def unpack_vector(blob: bytes) -> np.ndarray:
    (n,) = struct.unpack_from("I", blob, 0)
    vals = struct.unpack_from(f"{n}f", blob, 4)
    return np.asarray(vals, dtype=np.float32)


EMB_DDL = """
CREATE TABLE IF NOT EXISTS faculty_embedding (
    researcher_id INTEGER PRIMARY KEY,
    content_hash TEXT NOT NULL,
    backend TEXT NOT NULL,
    dim INTEGER NOT NULL,
    vector BLOB NOT NULL
);
"""


def ensure_embedding_table(conn: sqlite3.Connection) -> None:
    conn.executescript(EMB_DDL)


def faculty_document_text(conn: sqlite3.Connection, researcher_id: int) -> str:
    row = conn.execute(
        """
        SELECT r.display_name,
               (SELECT institution FROM affiliation a WHERE a.researcher_id=r.id AND a.is_current=1 LIMIT 1) AS institution,
               (SELECT GROUP_CONCAT(o.note, ' ') FROM opportunity o WHERE o.researcher_id=r.id) AS note,
               (SELECT GROUP_CONCAT(p.title || ' ' || IFNULL(p.abstract,''), ' ')
                  FROM publication p WHERE p.researcher_id=r.id) AS papers
        FROM researcher r WHERE r.id = ?
        """,
        (researcher_id,),
    ).fetchone()
    if not row:
        return ""
    return " ".join(filter(None, [row["display_name"], row["institution"], row["note"], row["papers"]]))


def rebuild_faculty_embeddings(conn: sqlite3.Connection, *, force: bool = False) -> dict:
    ensure_embedding_table(conn)
    ids = [r["id"] for r in conn.execute("SELECT id FROM researcher ORDER BY id").fetchall()]
    docs = []
    hashes = []
    to_embed_ids = []
    for rid in ids:
        text = faculty_document_text(conn, rid)
        h = content_hash(text)
        hashes.append(h)
        if not force:
            existing = conn.execute(
                "SELECT content_hash FROM faculty_embedding WHERE researcher_id=?",
                (rid,),
            ).fetchone()
            if existing and existing["content_hash"] == h:
                continue
        to_embed_ids.append(rid)
        docs.append(text)
    backend = "bow"
    if docs:
        vectors, backend = embed_texts(docs)
        for i, rid in enumerate(to_embed_ids):
            vec = vectors[i]
            conn.execute(
                """
                INSERT INTO faculty_embedding(researcher_id, content_hash, backend, dim, vector)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(researcher_id) DO UPDATE SET
                    content_hash=excluded.content_hash,
                    backend=excluded.backend,
                    dim=excluded.dim,
                    vector=excluded.vector
                """,
                (rid, content_hash(docs[i]), backend, int(vec.shape[0]), pack_vector(vec)),
            )
    return {"indexed": len(ids), "updated": len(to_embed_ids), "backend": backend}


def semantic_search(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 50,
) -> list[tuple[int, float]]:
    ensure_embedding_table(conn)
    rows = conn.execute(
        "SELECT researcher_id, vector FROM faculty_embedding"
    ).fetchall()
    if not rows:
        rebuild_faculty_embeddings(conn)
        rows = conn.execute(
            "SELECT researcher_id, vector FROM faculty_embedding"
        ).fetchall()
    if not rows:
        return []
    qvec, _ = embed_texts([query])
    q = qvec[0]
    scored: list[tuple[int, float]] = []
    for row in rows:
        v = unpack_vector(row["vector"])
        if v.shape[0] != q.shape[0]:
            # Backend changed (bow vs fastembed) — skip until rebuild
            continue
        scored.append((int(row["researcher_id"]), float(np.dot(q, v))))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[: int(limit)]
