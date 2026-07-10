from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from coeus.core.config import LlmProviderName, Settings
from coeus.core.errors import AppError
from coeus.persistence.state_store import StateStore
from coeus.services.audit import AuditLog

AI_MODEL_NAMESPACE = "ai_model"


@dataclass(frozen=True)
class AiModelState:
    provider: str
    active_model: str
    available_models: tuple[str, ...]
    api_key_configured: bool
    embedding_provider: str
    embedded_product_count: int
    changed_by: str | None
    changed_at: datetime | None


@dataclass(frozen=True)
class _AiModelSnapshot:
    provider: LlmProviderName
    active_model: str
    api_key: str | None
    changed_by: str | None
    changed_at: datetime | None


class AiModelService:
    """Administrator-controlled Gemini API runtime settings used by agents.

    The API key is write-only over the admin API: held server-side and never
    returned to clients. UI-configured keys are runtime-only so generic local
    state stores and database backups do not become secret stores.
    """

    def __init__(
        self,
        settings: Settings,
        audit_log: AuditLog,
        state_store: StateStore | None = None,
    ) -> None:
        self._audit_log = audit_log
        self._state_store = state_store
        self._provider = settings.llm_provider
        self._embedding_provider = settings.embedding_provider
        self._embedded_product_count: Callable[[], int] = lambda: 0
        self._available_models = tuple(settings.available_gemini_models)
        default_model = settings.gemini_api_model
        self._active_model = (
            default_model if default_model in self._available_models else self._available_models[0]
        )
        self._api_key = settings.gemini_api_key
        self._changed_by: str | None = None
        self._changed_at: datetime | None = None
        self._restore_or_persist(settings)

    def state(self) -> AiModelState:
        return AiModelState(
            provider=self.provider(),
            active_model=self._active_model,
            available_models=self._available_models,
            api_key_configured=bool(self._api_key),
            embedding_provider=self._embedding_provider,
            embedded_product_count=self._embedded_product_count(),
            changed_by=self._changed_by,
            changed_at=self._changed_at,
        )

    def provider(self) -> str:
        return self._provider

    def active_model(self) -> str:
        return self._active_model

    def api_key(self) -> str | None:
        return self._api_key

    def set_embedded_product_count_provider(self, provider: Callable[[], int]) -> None:
        self._embedded_product_count = provider

    def select(self, actor_user_id: str, actor_username: str, model: str) -> AiModelState:
        if model not in self._available_models:
            raise AppError(422, "model_not_available", "The requested model is not available.")
        if model == self._active_model:
            return self.state()
        snapshot = self._snapshot()
        try:
            previous = self._active_model
            self._active_model = model
            self._changed_by = actor_username
            self._changed_at = datetime.now(UTC)
            self._persist()
            self._audit_log.record(
                "ai_model_changed",
                actor_user_id,
                {"previous_model": previous, "active_model": model},
            )
        except Exception:
            self._restore(snapshot)
            self._persist()
            raise
        return self.state()

    def configure_api_key(
        self,
        actor_user_id: str,
        actor_username: str,
        api_key: str,
    ) -> AiModelState:
        # Configuring a key through the admin API is an explicit opt-in to the
        # Gemini provider. A key supplied only through the environment never
        # overrides COEUS_LLM_PROVIDER.
        snapshot = self._snapshot()
        try:
            self._api_key = api_key
            self._provider = "gemini_api"
            self._changed_by = actor_username
            self._changed_at = datetime.now(UTC)
            self._persist()
            self._audit_log.record(
                "ai_api_key_configured", actor_user_id, {"provider": "gemini_api"}
            )
        except Exception:
            self._restore(snapshot)
            self._persist()
            raise
        return self.state()

    def _restore_or_persist(self, settings: Settings) -> None:
        if self._state_store is None:
            return
        payload = self._state_store.load(AI_MODEL_NAMESPACE)
        if payload is None:
            self._persist()
            return
        needs_secret_scrub = "api_key" in payload
        active_model = str(payload.get("active_model", self._active_model))
        if active_model in self._available_models:
            self._active_model = active_model
        self._changed_by = payload.get("changed_by") if payload.get("changed_by") else None
        changed_at = payload.get("changed_at")
        self._changed_at = datetime.fromisoformat(str(changed_at)) if changed_at else None
        if needs_secret_scrub:
            self._persist()

    def _persist(self) -> None:
        if self._state_store is None:
            return
        self._state_store.save(
            AI_MODEL_NAMESPACE,
            {
                "active_model": self._active_model,
                "changed_by": self._changed_by,
                "changed_at": self._changed_at.isoformat() if self._changed_at else None,
            },
        )

    def _snapshot(self) -> _AiModelSnapshot:
        return _AiModelSnapshot(
            provider=self._provider,
            active_model=self._active_model,
            api_key=self._api_key,
            changed_by=self._changed_by,
            changed_at=self._changed_at,
        )

    def _restore(self, snapshot: _AiModelSnapshot) -> None:
        self._provider = snapshot.provider
        self._active_model = snapshot.active_model
        self._api_key = snapshot.api_key
        self._changed_by = snapshot.changed_by
        self._changed_at = snapshot.changed_at
