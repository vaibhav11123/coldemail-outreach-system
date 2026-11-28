"""Local faculty search: FTS5 + optional embeddings + RRF hybrid ranking."""

from studio.search.hybrid import hybrid_search_researchers
from studio.search.fts import rebuild_faculty_fts, search_faculty_fts

__all__ = [
    "rebuild_faculty_fts",
    "search_faculty_fts",
    "hybrid_search_researchers",
]
