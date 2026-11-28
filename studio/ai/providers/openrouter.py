"""OpenRouter OAuth PKCE — free models / student credits, no manual key copy."""

from __future__ import annotations

from urllib.parse import quote

import requests

from studio.ai.oauth_pkce import (
    code_challenge_s256,
    new_code_verifier,
    new_state,
    openrouter_auth_url,
    openrouter_headless_auth_url,
)
from studio.ai.types import (
    ConnectionResult,
    EvidenceBoundRequest,
    ModelInfo,
    ProviderStatus,
    RewriteResult,
)
from studio.secrets_store import delete_secret, get_secret, set_secret

PROVIDER_ID = "openrouter"
KEY_SECRET = "ai_openrouter_key"
USER_SECRET = "ai_openrouter_user"
VERIFIER_SECRET = "ai_openrouter_pkce_verifier"
STATE_SECRET = "ai_openrouter_pkce_state"

# Prefer free models first when listing; student can change later
DEFAULT_MODEL = "openrouter/free"


class OpenRouterProvider:
    id = PROVIDER_ID
    display_name = "Free AI (OpenRouter)"
    blurb = "OAuth alternative — your OpenRouter free models and credits."
    auth_kind = "oauth"
    priority = 2
    recommended = True
    card_title = "Free AI (OpenRouter)"
    card_subtitle = "OAuth — your OpenRouter allowance"

    def get_status(self) -> ProviderStatus:
        key = get_secret(KEY_SECRET)
        user = get_secret(USER_SECRET) or ""
        hint = ""
        if key:
            hint = f"…{key[-4:]}" if len(key) >= 4 else "connected"
            if user:
                hint = f"{user} · key {hint}"
        return ProviderStatus(
            id=self.id,
            connected=bool(key),
            label=self.display_name,
            detail="Ready to rewrite with your OpenRouter allowance."
            if key
            else "Connect to use free models (limits apply) or your OpenRouter credits.",
            auth_kind="oauth",
            account_hint=hint,
            models=self.list_models() if key else [],
            can_rewrite=bool(key),
            commercial_note="Inference is billed to the student's OpenRouter account or free quota.",
        )

    def connect_start(self, callback_base: str) -> ConnectionResult:
        verifier = new_code_verifier()
        challenge = code_challenge_s256(verifier)
        state = new_state()
        set_secret(VERIFIER_SECRET, verifier)
        set_secret(STATE_SECRET, state)
        callback = f"{callback_base.rstrip('/')}/ai/callback/openrouter"
        url = openrouter_auth_url(callback, challenge, state)
        return ConnectionResult(
            ok=True,
            provider_id=self.id,
            message="Open OpenRouter in your browser to authorize.",
            redirect_url=url,
        )

    def connect_headless_start(self) -> ConnectionResult:
        verifier = new_code_verifier()
        challenge = code_challenge_s256(verifier)
        set_secret(VERIFIER_SECRET, verifier)
        url = openrouter_headless_auth_url(challenge)
        return ConnectionResult(
            ok=True,
            provider_id=self.id,
            message="Authorize in the browser, then paste the code here.",
            redirect_url=url,
            needs_paste_code=True,
        )

    def connect_finish(self, **kwargs) -> ConnectionResult:
        code = (kwargs.get("code") or "").strip()
        state = (kwargs.get("state") or "").strip()
        if not code:
            return ConnectionResult(ok=False, provider_id=self.id, message="Missing authorization code.")
        expected_state = get_secret(STATE_SECRET)
        if expected_state and state and state != expected_state:
            return ConnectionResult(ok=False, provider_id=self.id, message="OAuth state mismatch. Try again.")
        verifier = get_secret(VERIFIER_SECRET)
        if not verifier:
            return ConnectionResult(
                ok=False,
                provider_id=self.id,
                message="Authorization expired. Start Connect free AI again.",
            )
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/auth/keys",
                json={
                    "code": code,
                    "code_verifier": verifier,
                    "code_challenge_method": "S256",
                },
                timeout=30,
            )
        except requests.RequestException as exc:
            return ConnectionResult(ok=False, provider_id=self.id, message=f"Network error: {exc}")
        if resp.status_code >= 400:
            return ConnectionResult(
                ok=False,
                provider_id=self.id,
                message=f"OpenRouter refused the code ({resp.status_code}). Try again.",
            )
        data = resp.json() if resp.content else {}
        key = data.get("key") or data.get("api_key")
        if not key:
            return ConnectionResult(ok=False, provider_id=self.id, message="No key returned by OpenRouter.")
        set_secret(KEY_SECRET, key)
        if data.get("user_id"):
            set_secret(USER_SECRET, str(data["user_id"]))
        delete_secret(VERIFIER_SECRET)
        delete_secret(STATE_SECRET)
        return ConnectionResult(
            ok=True,
            provider_id=self.id,
            message="Free AI connected. Credentials stay on this device.",
        )

    def disconnect(self) -> None:
        for name in (KEY_SECRET, USER_SECRET, VERIFIER_SECRET, STATE_SECRET):
            delete_secret(name)

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="openrouter/free", label="Free models (rotating)", free=True),
            ModelInfo(id="meta-llama/llama-3.2-3b-instruct:free", label="Llama 3.2 3B free", free=True),
            ModelInfo(id="google/gemma-2-9b-it:free", label="Gemma 2 9B free", free=True),
        ]

    def rewrite(self, request: EvidenceBoundRequest) -> RewriteResult:
        key = get_secret(KEY_SECRET)
        if not key:
            return RewriteResult(ok=False, error="OpenRouter not connected", provider_id=self.id)
        model = get_secret("ai_openrouter_model") or DEFAULT_MODEL
        evidence = "\n".join(f"- {s}" for s in request.evidence_snippets if s)
        prompt = (
            "Rephrase this research outreach letter. "
            "Only rephrase; do not add claims, names, papers, numbers, or URLs.\n\n"
            f"Evidence you may reference:\n{evidence}\n\n"
            f"Subject: {request.subject}\n\nBody:\n{request.body}"
        )
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://academic-outreach.studio",
                    "X-Title": "Academic Outreach Studio",
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You rephrase research emails. Never invent papers, names, "
                                "numbers, or URLs. Keep every existing URL verbatim."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=60,
            )
        except requests.RequestException as exc:
            return RewriteResult(ok=False, error=str(exc), provider_id=self.id)
        if resp.status_code == 429:
            return RewriteResult(
                ok=False,
                error="OpenRouter rate limit or free quota spent for today.",
                provider_id=self.id,
            )
        if resp.status_code >= 400:
            return RewriteResult(
                ok=False,
                error=f"OpenRouter HTTP {resp.status_code}",
                provider_id=self.id,
            )
        data = resp.json()
        try:
            body = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError):
            return RewriteResult(ok=False, error="Unexpected OpenRouter response", provider_id=self.id)
        return RewriteResult(
            ok=True,
            subject=request.subject,
            body=body,
            provider_id=self.id,
            model=model,
        )


def mask_for_logs(text: str) -> str:
    return quote(text[:0])  # never log bodies
