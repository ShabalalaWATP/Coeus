from dataclasses import dataclass
from datetime import UTC, datetime

from coeus.core.config import Settings
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
        self._available_models = tuple(settings.available_gemini_models)
        default_model = (
            settings.gemma_vertex_model
            if settings.llm_provider == "gemma_vertex"
            else settings.gemini_api_model
        )
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
            changed_by=self._changed_by,
            changed_at=self._changed_at,
        )

    def provider(self) -> str:
        return "gemini_api" if self._api_key else self._provider

    def active_model(self) -> str:
        return self._active_model

    def api_key(self) -> str | None:
        return self._api_key

    def select(self, actor_user_id: str, actor_username: str, model: str) -> AiModelState:
        if model not in self._available_models:
            raise AppError(422, "model_not_available", "The requested model is not available.")
        previous = self._active_model
        self._active_model = model
        self._changed_by = actor_username
        self._changed_at = datetime.now(UTC)
        self._audit_log.record(
            "ai_model_changed",
            actor_user_id,
            {"previous_model": previous, "active_model": model},
        )
        self._persist()
        return self.state()

    def configure_api_key(
        self,
        actor_user_id: str,
        actor_username: str,
        api_key: str,
    ) -> AiModelState:
        self._api_key = api_key
        self._changed_by = actor_username
        self._changed_at = datetime.now(UTC)
        self._audit_log.record("ai_api_key_configured", actor_user_id, {"provider": "gemini_api"})
        self._persist()
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
