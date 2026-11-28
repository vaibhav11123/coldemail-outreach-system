"""Groq Connect Assistant — user-authorized BYOG onboarding.

Explicit credential transfer only. No dashboard scraping, session cookies,
undocumented account APIs, or invented OAuth endpoints.
"""

from studio.connections.groq.connection_state import ConnectionPhase, get_phase, set_phase
from studio.connections.groq.onboarding import (
    AssistantView,
    cancel_setup,
    complete_with_pasted_key,
    import_local_env_key_with_consent,
    peek_local_env_key,
    start_assistant,
    status_summary,
)

__all__ = [
    "AssistantView",
    "ConnectionPhase",
    "cancel_setup",
    "complete_with_pasted_key",
    "get_phase",
    "import_local_env_key_with_consent",
    "peek_local_env_key",
    "set_phase",
    "start_assistant",
    "status_summary",
]
