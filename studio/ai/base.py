"""Provider protocol — one rewrite engine, many auth adapters."""

from __future__ import annotations

from typing import Protocol

from studio.ai.types import ConnectionResult, EvidenceBoundRequest, ModelInfo, ProviderStatus, RewriteResult


class AIProvider(Protocol):
    id: str
    display_name: str
    blurb: str
    auth_kind: str
    priority: int  # lower = show first
    recommended: bool

    def get_status(self) -> ProviderStatus: ...

    def connect_start(self, callback_base: str) -> ConnectionResult: ...

    def connect_finish(self, **kwargs) -> ConnectionResult: ...

    def disconnect(self) -> None: ...

    def list_models(self) -> list[ModelInfo]: ...

    def rewrite(self, request: EvidenceBoundRequest) -> RewriteResult: ...
