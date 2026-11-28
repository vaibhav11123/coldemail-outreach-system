"""Unified Connections — zero mandatory accounts (CON-01)."""

from studio.connections.manager import (
    connection_requirements,
    list_connection_cards,
    prefill_email_candidates,
    sections_for_ui,
    status_for,
    workspace_setup_steps,
)
from studio.connections.registry import all_specs, spec_by_id

__all__ = [
    "all_specs",
    "connection_requirements",
    "list_connection_cards",
    "prefill_email_candidates",
    "sections_for_ui",
    "spec_by_id",
    "status_for",
    "workspace_setup_steps",
]
