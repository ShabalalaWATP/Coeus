from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from coeus.core.config import LlmProviderName, Settings
from coeus.core.errors import AppError
from coeus.persistence.state_store import StateStore
from coeus.services.ai_provider_catalog import (
    ProviderSpec,
    initial_api_keys,
    provider_specs,
    spec_for,
)
from coeus.services.audit import AuditLog

AI_MODEL_NAMESPACE = "ai_model"


@dataclass(frozen=True)
class AiProviderState:
    name: str
    label: str
    models: tuple[str, ...]
    active_model: str
    api_key_configured: bool


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
    providers: tuple[AiProviderState, ...]


@dataclass(frozen=True)
class _AiModelSnapshot:
    provider: LlmProviderName
    active_models: dict[str, str]
    api_keys: dict[str, str | None]
    changed_by: str | None
    changed_at: datetime | None


class AiModelService:
    """Administrator-controlled LLM provider and model selection.

    One instance serves the whole application, so switching the provider or
    model takes effect for every user immediately. API keys are write-only
    over the admin API: held server-side, never returned to clients and
    never persisted, so generic local state stores and database backups do
    not become secret stores.
    """

    def __init__(
        self,
        settings: Settings,
        audit_log: AuditLog,
        state_store: StateStore | None = None,
    ) -> None:
        self._settings = settings
        self._audit_log = audit_log
        self._state_store = state_store
        self._provider: LlmProviderName = settings.llm_provider
        self._embedding_provider = settings.embedding_provider
        self._embedded_product_count: Callable[[], int] = lambda: 0
        self._api_keys = initial_api_keys(settings)
        self._active_models = {spec.name: spec.default_model for spec in provider_specs(settings)}
        self._changed_by: str | None = None
        self._changed_at: datetime | None = None
        self._restore_or_persist()

    def state(self) -> AiModelState:
        active_spec = self._spec(self._provider)
        return AiModelState(
            provider=self.provider(),
            active_model=self.active_model(),
            available_models=active_spec.models if active_spec else (),
            api_key_configured=bool(self._api_keys.get(self._provider)),
            embedding_provider=self._embedding_provider,
            embedded_product_count=self._embedded_product_count(),
            changed_by=self._changed_by,
            changed_at=self._changed_at,
            providers=tuple(
                AiProviderState(
                    name=spec.name,
                    label=spec.label,
                    models=spec.models,
                    active_model=self._active_models[spec.name],
                    api_key_configured=bool(self._api_keys.get(spec.name)),
                )
                for spec in provider_specs(self._settings)
            ),
        )

    def provider(self) -> str:
        return self._provider

    def active_model(self, provider: str | None = None) -> str:
        return self._active_models[provider or self._provider]

    def api_key(self, provider: str | None = None) -> str | None:
        return self._api_keys.get(provider or self._provider)

    def set_embedded_product_count_provider(self, provider: Callable[[], int]) -> None:
        self._embedded_product_count = provider

    def select(
        self,
        actor_user_id: str,
        actor_username: str,
        model: str,
        provider: str | None = None,
    ) -> AiModelState:
        spec = self._spec(provider or self._provider)
        if spec is None or model not in spec.models:
            raise AppError(422, "model_not_available", "The requested model is not available.")
        if model == self._active_models[spec.name]:
            return self.state()
        previous = self._active_models[spec.name]
        self._apply_change(
            actor_user_id,
            actor_username,
            "ai_model_changed",
            {"provider": spec.name, "previous_model": previous, "active_model": model},
            lambda: self._active_models.__setitem__(spec.name, model),
        )
        return self.state()

    def select_provider(
        self, actor_user_id: str, actor_username: str, provider: str
    ) -> AiModelState:
        spec = self._spec(provider)
        if spec is None:
            raise AppError(
                422, "provider_not_available", "The requested provider is not available."
            )
        if spec.name != "mock" and not self._api_keys.get(spec.name):
            raise AppError(
                422,
                "provider_not_configured",
                "Configure an API key for the provider before activating it.",
            )
        if spec.name == self._provider:
            return self.state()
        previous = self._provider
        self._apply_change(
            actor_user_id,
            actor_username,
            "ai_provider_changed",
            {
                "previous_provider": previous,
                "provider": spec.name,
                "active_model": self._active_models[spec.name],
            },
            lambda: setattr(self, "_provider", spec.name),
        )
        return self.state()

    def configure_api_key(
        self,
        actor_user_id: str,
        actor_username: str,
        api_key: str,
        provider: str = "gemini_api",
    ) -> AiModelState:
        # Saving a key stores it for that provider only; activating the
        # provider is a separate, explicit (and warned) admin action.
        spec = self._spec(provider)
        if spec is None or spec.name == "mock":
            raise AppError(
                422, "provider_not_available", "The requested provider is not available."
            )
        self._apply_change(
            actor_user_id,
            actor_username,
            "ai_api_key_configured",
            {"provider": spec.name},
            lambda: self._api_keys.__setitem__(spec.name, api_key),
        )
        return self.state()

    def _apply_change(
        self,
        actor_user_id: str,
        actor_username: str,
        event_type: str,
        metadata: dict[str, str],
        mutate: Callable[[], None],
    ) -> None:
        snapshot = self._snapshot()
        try:
            mutate()
            self._changed_by = actor_username
            self._changed_at = datetime.now(UTC)
            self._persist()
            self._audit_log.record(event_type, actor_user_id, metadata)
        except Exception:
            self._restore(snapshot)
            self._persist()
            raise

    def _spec(self, provider: str) -> ProviderSpec | None:
        return spec_for(self._settings, provider)

    def _restore_or_persist(self) -> None:
        if self._state_store is None:
            return
        payload = self._state_store.load(AI_MODEL_NAMESPACE)
        if payload is None:
            self._persist()
            return
        needs_secret_scrub = "api_key" in payload
        stored_models = payload.get("active_models")
        if isinstance(stored_models, dict):
            for name, model in stored_models.items():
                spec = self._spec(str(name))
                if spec is not None and model in spec.models:
                    self._active_models[spec.name] = str(model)
        # Pre-multi-provider payloads stored a single Gemini model.
        legacy_model = str(payload.get("active_model", ""))
        gemini = self._spec("gemini_api")
        if not isinstance(stored_models, dict) and gemini and legacy_model in gemini.models:
            self._active_models["gemini_api"] = legacy_model
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
                "active_model": self._active_models[self._provider],
                "active_models": dict(self._active_models),
                "changed_by": self._changed_by,
                "changed_at": self._changed_at.isoformat() if self._changed_at else None,
            },
        )

    def _snapshot(self) -> _AiModelSnapshot:
        return _AiModelSnapshot(
            provider=self._provider,
            active_models=dict(self._active_models),
            api_keys=dict(self._api_keys),
            changed_by=self._changed_by,
            changed_at=self._changed_at,
        )

    def _restore(self, snapshot: _AiModelSnapshot) -> None:
        self._provider = snapshot.provider
        self._active_models = dict(snapshot.active_models)
        self._api_keys = dict(snapshot.api_keys)
        self._changed_by = snapshot.changed_by
        self._changed_at = snapshot.changed_at
