"""Connection state machine for the Groq Connect Assistant."""

from __future__ import annotations

from enum import Enum

from studio.secrets_store import delete_secret, get_secret, set_secret

PHASE_SECRET = "groq_connect_phase"
DETAIL_SECRET = "groq_connect_detail"


class ConnectionPhase(str, Enum):
    IDLE = "idle"
    LAUNCHING_DASHBOARD = "launching_dashboard"
    AWAITING_SIGNIN = "awaiting_signin"
    AWAITING_KEY_CREATION = "awaiting_key_creation"
    AWAITING_CREDENTIAL_IMPORT = "awaiting_credential_import"
    LOCAL_KEY_DETECTED = "local_key_detected"
    VALIDATING = "validating"
    DISCOVERING_MODELS = "discovering_models"
    STORING = "storing"
    CONNECTED = "connected"
    INVALID_CREDENTIAL = "invalid_credential"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXHAUSTED = "quota_exhausted"
    REVOKED = "revoked"
    CANCELLED = "cancelled"
    RECONNECTING = "reconnecting"
    PROVIDER_UNAVAILABLE = "provider_unavailable"


_PHASE_LABELS = {
    ConnectionPhase.IDLE: "Ready to connect",
    ConnectionPhase.LAUNCHING_DASHBOARD: "Opening GroqCloud…",
    ConnectionPhase.AWAITING_SIGNIN: "Sign in to GroqCloud",
    ConnectionPhase.AWAITING_KEY_CREATION: "Create a dedicated key",
    ConnectionPhase.AWAITING_CREDENTIAL_IMPORT: "Paste your key to finish",
    ConnectionPhase.LOCAL_KEY_DETECTED: "Local Groq key found — confirm import",
    ConnectionPhase.VALIDATING: "Validating with GroqCloud…",
    ConnectionPhase.DISCOVERING_MODELS: "Selecting a supported model…",
    ConnectionPhase.STORING: "Saving to your device keychain…",
    ConnectionPhase.CONNECTED: "Connected",
    ConnectionPhase.INVALID_CREDENTIAL: "That key was rejected",
    ConnectionPhase.RATE_LIMITED: "Rate limited — try again shortly",
    ConnectionPhase.QUOTA_EXHAUSTED: "Quota exhausted on this Groq account",
    ConnectionPhase.REVOKED: "Key revoked — reconnect required",
    ConnectionPhase.CANCELLED: "Setup cancelled",
    ConnectionPhase.RECONNECTING: "Reconnect GroqCloud",
    ConnectionPhase.PROVIDER_UNAVAILABLE: "GroqCloud temporarily unreachable",
}


def get_phase() -> ConnectionPhase:
    raw = (get_secret(PHASE_SECRET) or ConnectionPhase.IDLE.value).strip()
    try:
        return ConnectionPhase(raw)
    except ValueError:
        return ConnectionPhase.IDLE


def get_detail() -> str:
    return get_secret(DETAIL_SECRET) or ""


def set_phase(phase: ConnectionPhase, detail: str = "") -> None:
    set_secret(PHASE_SECRET, phase.value)
    if detail:
        set_secret(DETAIL_SECRET, detail)
    elif get_secret(DETAIL_SECRET) and phase in {
        ConnectionPhase.IDLE,
        ConnectionPhase.CONNECTED,
        ConnectionPhase.CANCELLED,
    }:
        delete_secret(DETAIL_SECRET)


def phase_label(phase: ConnectionPhase | None = None) -> str:
    p = phase or get_phase()
    return _PHASE_LABELS.get(p, p.value)


def clear_ephemeral() -> None:
    delete_secret(PHASE_SECRET)
    delete_secret(DETAIL_SECRET)
