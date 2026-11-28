"""Groq Connect Assistant orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

from studio.connections.groq import browser_launcher, credential_import, keychain
from studio.connections.groq.connection_state import (
    ConnectionPhase,
    clear_ephemeral,
    get_detail,
    get_phase,
    phase_label,
    set_phase,
)
from studio.connections.groq.credential_validator import validate_api_key
from studio.connections.groq.model_discovery import describe_models, pick_model
from studio.connections.groq.quota_manager import record_rate_limit_hint


@dataclass
class AssistantView:
    phase: ConnectionPhase
    phase_label: str
    title: str
    subtitle: str
    bullets: list[str]
    steps: list[str]
    message: str
    detail: str
    dashboard_url: str
    docs_url: str
    connected: bool
    account_hint: str
    selected_model: str
    models: list[dict] = field(default_factory=list)
    local_env: dict = field(default_factory=dict)
    can_paste: bool = True
    can_launch: bool = True
    can_cancel: bool = True
    can_import_local: bool = False
    compliance_note: str = (
        "We only use credentials you explicitly provide. "
        "We do not read Groq session cookies, scrape the dashboard, "
        "or call undocumented account APIs. This is not OAuth."
    )


def _base_bullets() -> list[str]:
    return [
        "No credit card required for the free tier",
        "No technical configuration",
        "Your own inference allowance",
        "Credentials stored on your device",
    ]


def _default_steps() -> list[str]:
    return [
        "Open the official GroqCloud dashboard and sign in.",
        "Create a dedicated API key named Academic Outreach Studio.",
        "Copy the key, return here, and paste it once.",
        "We validate it, pick a model, and store it in your OS keychain.",
    ]


def status_summary() -> dict:
    connected = keychain.is_connected()
    phase = ConnectionPhase.CONNECTED if connected else get_phase()
    if connected and phase not in {ConnectionPhase.CONNECTED, ConnectionPhase.RATE_LIMITED}:
        phase = ConnectionPhase.CONNECTED
    return {
        "connected": connected,
        "phase": phase.value,
        "phase_label": phase_label(phase),
        "detail": get_detail(),
        "account_hint": keychain.account_hint(),
        "model": keychain.get_selected_model() if connected else "",
        "rate_limit_note": record_rate_limit_hint(),
    }


def start_assistant(*, launch_browser: bool = False) -> AssistantView:
    """Enter the guided connection flow. Optionally open GroqCloud.

    Merely opening the assistant page does not advance past IDLE — that kept
    Connections stuck on \"Paste your key to finish\". Launch or paste advances.
    """
    if keychain.is_connected():
        set_phase(ConnectionPhase.CONNECTED)
        return build_view()

    local = credential_import.peek_local_env_key()
    if local.get("found") and get_phase() in {
        ConnectionPhase.IDLE,
        ConnectionPhase.CANCELLED,
        ConnectionPhase.LOCAL_KEY_DETECTED,
    }:
        set_phase(
            ConnectionPhase.LOCAL_KEY_DETECTED,
            "A GROQ_API_KEY is already set on this computer. Import it with your permission, or create a new key in GroqCloud.",
        )

    if launch_browser:
        set_phase(ConnectionPhase.LAUNCHING_DASHBOARD)
        browser_launcher.launch_official_dashboard()
        set_phase(
            ConnectionPhase.AWAITING_CREDENTIAL_IMPORT,
            "GroqCloud opened. After you create a key, paste it below.",
        )

    return build_view()


def cancel_setup() -> AssistantView:
    if not keychain.is_connected():
        set_phase(ConnectionPhase.CANCELLED, "Setup cancelled. You can connect later anytime.")
        clear_ephemeral()
        set_phase(ConnectionPhase.IDLE)
    return build_view()


def complete_with_pasted_key(raw_key: str) -> tuple[bool, str, AssistantView]:
    imported = credential_import.from_explicit_paste(raw_key)
    if not imported:
        set_phase(ConnectionPhase.INVALID_CREDENTIAL, "Paste the key from GroqCloud.")
        return False, "Paste the key from GroqCloud.", build_view()
    return _finish_import(imported.key, source=imported.source)


def import_local_env_key_with_consent(*, consented: bool) -> tuple[bool, str, AssistantView]:
    if not consented:
        set_phase(
            ConnectionPhase.AWAITING_CREDENTIAL_IMPORT,
            "Local key not imported. Create a key in GroqCloud or paste one below.",
        )
        return False, "Import cancelled.", build_view()
    imported = credential_import.from_local_env_with_consent(consented=True)
    if not imported:
        set_phase(ConnectionPhase.INVALID_CREDENTIAL, "No GROQ_API_KEY found in the environment.")
        return False, "No local GROQ_API_KEY found.", build_view()
    return _finish_import(imported.key, source=imported.source)


def peek_local_env_key() -> dict:
    return credential_import.peek_local_env_key()


def _finish_import(api_key: str, *, source: str) -> tuple[bool, str, AssistantView]:
    set_phase(ConnectionPhase.VALIDATING, "Checking your key with GroqCloud…")
    result = validate_api_key(api_key)
    if not result.ok:
        if result.kind == "rate_limited":
            set_phase(ConnectionPhase.RATE_LIMITED, result.message)
        elif result.kind == "unreachable":
            set_phase(ConnectionPhase.PROVIDER_UNAVAILABLE, result.message)
        else:
            set_phase(ConnectionPhase.INVALID_CREDENTIAL, result.message)
        return False, result.message, build_view()

    set_phase(ConnectionPhase.DISCOVERING_MODELS, "Choosing a supported model…")
    model = pick_model(result.models)
    set_phase(ConnectionPhase.STORING, "Saving to your device keychain…")
    keychain.store_validated_key(api_key, model, source=source)
    set_phase(
        ConnectionPhase.CONNECTED,
        f"Connected. Using model {model}. Inference uses your GroqCloud allowance.",
    )
    msg = f"{result.message} Using model {model}."
    return True, msg, build_view()


def mark_rewrite_failure(kind: str, message: str) -> None:
    if kind == "revoked":
        keychain.mark_revoked()
        set_phase(ConnectionPhase.REVOKED, message)
    elif kind == "rate_limited":
        set_phase(ConnectionPhase.RATE_LIMITED, message)
    elif kind == "quota_exhausted":
        set_phase(ConnectionPhase.QUOTA_EXHAUSTED, message)
    elif kind == "unavailable":
        set_phase(ConnectionPhase.PROVIDER_UNAVAILABLE, message)


def build_view() -> AssistantView:
    summary = status_summary()
    phase = ConnectionPhase(summary["phase"])
    local = credential_import.peek_local_env_key()
    connected = summary["connected"]
    models: list[dict] = []
    selected = ""
    if connected:
        selected = keychain.get_selected_model()
        models = describe_models([selected], selected)

    steps = _default_steps()
    if phase == ConnectionPhase.LOCAL_KEY_DETECTED:
        steps = [
            "Confirm import of the GROQ_API_KEY already on this computer, or",
            "Open GroqCloud and create a new dedicated key instead.",
            "We validate before storing anything in your keychain.",
        ]

    idle_msg = (
        "Open GroqCloud, create a dedicated key, then paste it here. "
        "No coding and no shared product account."
    )
    message = summary["detail"] or (
        idle_msg if (not connected and phase == ConnectionPhase.IDLE) else phase_label(phase)
    )

    return AssistantView(
        phase=phase,
        phase_label=(
            "Ready to connect"
            if phase == ConnectionPhase.IDLE and not connected
            else summary["phase_label"]
        ),
        title="Connect your free AI",
        subtitle="Powered by your own GroqCloud account.",
        bullets=_base_bullets(),
        steps=steps,
        message=message,
        detail=summary["detail"],
        dashboard_url=browser_launcher.official_keys_url(),
        docs_url=browser_launcher.official_docs_url(),
        connected=connected,
        account_hint=summary["account_hint"],
        selected_model=selected,
        models=models,
        local_env=local,
        can_paste=not connected,
        can_launch=not connected,
        can_cancel=not connected and phase not in {ConnectionPhase.IDLE, ConnectionPhase.CANCELLED},
        can_import_local=bool(local.get("found")) and not connected,
    )
