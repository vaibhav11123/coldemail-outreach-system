"""Normalize faculty records for packaging without mutating factual fields."""

from __future__ import annotations

from typing import Any


FACTUAL_FIELDS = (
    "canonical_id",
    "display_name",
    "email",
    "university",
    "status",
    "funding",
    "eligibility",
    "deadline",
    "apply_url",
    "email_invited",
    "note",
    "paper_title",
    "paper_year",
    "paper_url",
    "paper_abstract",
)


def records_from_sqlite(conn) -> list[dict[str, Any]]:
    """Pull bundled (or all) researchers into a flat packaging shape."""
    rows = conn.execute(
        """
        SELECT r.id AS rid,
               COALESCE(r.professor_key, 'id:' || r.id) AS canonical_id,
               r.display_name,
               r.email,
               (
                 SELECT institution FROM affiliation a
                 WHERE a.researcher_id = r.id AND a.is_current = 1
                 LIMIT 1
               ) AS university,
               (
                 SELECT o.status FROM opportunity o
                 WHERE o.researcher_id = r.id
                 ORDER BY o.id DESC LIMIT 1
               ) AS status,
               (
                 SELECT o.funding FROM opportunity o
                 WHERE o.researcher_id = r.id
                 ORDER BY o.id DESC LIMIT 1
               ) AS funding,
               (
                 SELECT o.eligibility FROM opportunity o
                 WHERE o.researcher_id = r.id
                 ORDER BY o.id DESC LIMIT 1
               ) AS eligibility,
               (
                 SELECT o.deadline FROM opportunity o
                 WHERE o.researcher_id = r.id
                 ORDER BY o.id DESC LIMIT 1
               ) AS deadline,
               (
                 SELECT o.apply_url FROM opportunity o
                 WHERE o.researcher_id = r.id
                 ORDER BY o.id DESC LIMIT 1
               ) AS apply_url,
               (
                 SELECT o.email_invited FROM opportunity o
                 WHERE o.researcher_id = r.id
                 ORDER BY o.id DESC LIMIT 1
               ) AS email_invited,
               (
                 SELECT o.note FROM opportunity o
                 WHERE o.researcher_id = r.id
                 ORDER BY o.id DESC LIMIT 1
               ) AS note,
               (
                 SELECT p.title FROM publication p
                 WHERE p.researcher_id = r.id
                 ORDER BY p.year DESC, p.id DESC LIMIT 1
               ) AS paper_title,
               (
                 SELECT p.year FROM publication p
                 WHERE p.researcher_id = r.id
                 ORDER BY p.year DESC, p.id DESC LIMIT 1
               ) AS paper_year,
               (
                 SELECT p.url FROM publication p
                 WHERE p.researcher_id = r.id
                 ORDER BY p.year DESC, p.id DESC LIMIT 1
               ) AS paper_url,
               (
                 SELECT p.abstract FROM publication p
                 WHERE p.researcher_id = r.id
                 ORDER BY p.year DESC, p.id DESC LIMIT 1
               ) AS paper_abstract
        FROM researcher r
        ORDER BY r.id
        """
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append({field: row[field] for field in FACTUAL_FIELDS})
    return out


def attach_export_ids(records: list[dict[str, Any]], export_ids: dict[str, str]) -> list[dict[str, Any]]:
    enriched = []
    for rec in records:
        copy = dict(rec)
        copy["export_id"] = export_ids[rec["canonical_id"]]
        enriched.append(copy)
    return enriched
