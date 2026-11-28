"""Public academic metadata adapters (no student login)."""

from studio.academic.crossref import lookup_doi
from studio.academic.opencitations import citations_for_doi
from studio.academic.orcid_local import lookup_orcid, search_name

__all__ = ["lookup_doi", "citations_for_doi", "lookup_orcid", "search_name"]
