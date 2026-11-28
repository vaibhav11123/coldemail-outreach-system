"""Local Ollama detection — private offline rewrite."""

from __future__ import annotations

import requests

from studio.ai.types import (
    ConnectionResult,
    EvidenceBoundRequest,
    ModelInfo,
    ProviderStatus,
    RewriteResult,
)
from studio.secrets_store import delete_secret, get_secret, set_secret

PROVIDER_ID = "ollama"
HOST_SECRET = "ai_ollama_host"
MODEL_SECRET = "ai_ollama_model"
DEFAULT_HOST = "http://127.0.0.1:11434"


class OllamaProvider:
    id = PROVIDER_ID
    display_name = "Local AI"
    blurb = "Private, offline inference on your computer."
    auth_kind = "detect"
    priority = 40
    recommended = False
    card_title = "Local AI"
    card_subtitle = "Private, offline inference"

    def get_status(self) -> ProviderStatus:
        host = get_secret(HOST_SECRET) or DEFAULT_HOST
        connected = False
        detail = "Ollama not detected on this computer."
        models: list[ModelInfo] = []
        try:
            resp = requests.get(f"{host.rstrip('/')}/api/tags", timeout=1.5)
            if resp.status_code == 200:
                connected = True
                names = [m.get("name") for m in resp.json().get("models", []) if m.get("name")]
                models = [ModelInfo(id=n, label=n, free=True) for n in names[:12]]
                detail = f"Detected at {host}." if names else f"Ollama is running at {host}, but no models are installed."
                if get_secret(HOST_SECRET):
                    detail = f"Connected · {host}"
        except requests.RequestException:
            connected = bool(get_secret(HOST_SECRET))
            if connected:
                detail = f"Saved {host}, but it is not responding right now."
        return ProviderStatus(
            id=self.id,
            connected=connected and bool(models or get_secret(HOST_SECRET)),
            label=self.display_name,
            detail=detail,
            auth_kind="detect",
            account_hint=host if connected else "",
            models=models,
            can_rewrite=connected and bool(models),
            commercial_note="Runs entirely on the student's machine.",
        )

    def connect_start(self, callback_base: str) -> ConnectionResult:
        host = DEFAULT_HOST
        try:
            resp = requests.get(f"{host}/api/tags", timeout=1.5)
            if resp.status_code != 200:
                return ConnectionResult(
                    ok=False,
                    provider_id=self.id,
                    message="Ollama is not running. Install it from ollama.com, pull a model, then Detect again.",
                    redirect_url="https://ollama.com/download",
                )
            names = [m.get("name") for m in resp.json().get("models", []) if m.get("name")]
            set_secret(HOST_SECRET, host)
            if names:
                set_secret(MODEL_SECRET, names[0])
            return ConnectionResult(
                ok=True,
                provider_id=self.id,
                message=f"Local AI connected ({len(names)} model(s)).",
            )
        except requests.RequestException:
            return ConnectionResult(
                ok=False,
                provider_id=self.id,
                message="Could not reach Ollama on 127.0.0.1:11434. Install and start it, then Detect again.",
                redirect_url="https://ollama.com/download",
            )

    def connect_finish(self, **kwargs) -> ConnectionResult:
        host = (kwargs.get("host") or DEFAULT_HOST).strip() or DEFAULT_HOST
        set_secret(HOST_SECRET, host.rstrip("/"))
        if kwargs.get("model"):
            set_secret(MODEL_SECRET, kwargs["model"].strip())
        return self.connect_start("")

    def disconnect(self) -> None:
        delete_secret(HOST_SECRET)
        delete_secret(MODEL_SECRET)

    def list_models(self) -> list[ModelInfo]:
        return self.get_status().models

    def rewrite(self, request: EvidenceBoundRequest) -> RewriteResult:
        host = get_secret(HOST_SECRET) or DEFAULT_HOST
        model = get_secret(MODEL_SECRET)
        if not model:
            status = self.get_status()
            if status.models:
                model = status.models[0].id
            else:
                return RewriteResult(ok=False, error="No local model installed", provider_id=self.id)
        prompt = (
            "Rephrase this research outreach letter. Do not add claims, names, papers, numbers, or URLs.\n\n"
            f"{request.body}"
        )
        try:
            resp = requests.post(
                f"{host.rstrip('/')}/api/chat",
                json={
                    "model": model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": "Rephrase only. Never invent facts."},
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=120,
            )
        except requests.RequestException as exc:
            return RewriteResult(ok=False, error=str(exc), provider_id=self.id)
        if resp.status_code >= 400:
            return RewriteResult(ok=False, error=f"Ollama HTTP {resp.status_code}", provider_id=self.id)
        data = resp.json()
        body = (data.get("message") or {}).get("content") or ""
        if not body.strip():
            return RewriteResult(ok=False, error="Empty Ollama response", provider_id=self.id)
        return RewriteResult(
            ok=True, subject=request.subject, body=body.strip(), provider_id=self.id, model=model
        )
