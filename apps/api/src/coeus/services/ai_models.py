from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from coeus.core.config import LlmProviderName, Settings
from coeus.core.errors import AppError
from coeus.core.model_ids import MAX_MODELS_PER_SOURCE, clean_model_ids, is_valid_model_id
from coeus.integrations.llm_models import discover_models
from coeus.persistence.state_store import StateStore
from coeus.services.ai_model_state import model_state_payload, restore_model_state
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
    supports_model_refresh: bool


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
    active_models: dict[LlmProviderName, str]
    custom_models: dict[str, list[str]]
    discovered_models: dict[str, list[str]]
    api_keys: dict[LlmProviderName, str | None]
    changed_by: str | None
    changed_at: datetime | None


class AiModelService:
    """Administrator-controlled, application-wide LLM configuration."""

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
        specs = provider_specs(settings)
        self._active_models = {spec.name: spec.default_model for spec in specs}
        self._custom_models: dict[str, list[str]] = {spec.name: [] for spec in specs}
        self._discovered_models: dict[str, list[str]] = {spec.name: [] for spec in specs}
        self._changed_by: str | None = None
        self._changed_at: datetime | None = None
        self._restore_or_persist()

    def state(self) -> AiModelState:
        return AiModelState(
            provider=self.provider(),
            active_model=self.active_model(),
            available_models=self._effective_models(self._provider),
            api_key_configured=bool(self._api_keys.get(self._provider)),
            embedding_provider=self._embedding_provider,
            embedded_product_count=self._embedded_product_count(),
            changed_by=self._changed_by,
            changed_at=self._changed_at,
            providers=tuple(self._provider_state(spec) for spec in provider_specs(self._settings)),
        )

    def _provider_state(self, spec: ProviderSpec) -> AiProviderState:
        return AiProviderState(
            name=spec.name,
            label=spec.label,
            models=self._effective_models(spec.name),
            active_model=self._active_models[spec.name],
            api_key_configured=bool(self._api_keys.get(spec.name)),
            supports_model_refresh=spec.supports_model_refresh,
        )

    def _effective_models(self, provider: str) -> tuple[str, ...]:
        spec = self._spec(provider)
        if spec is None:
            return ()
        return tuple(
            dict.fromkeys(
                [
                    *spec.models,
                    *self._custom_models.get(provider, []),
                    *self._discovered_models.get(provider, []),
                ]
            )
        )

    def provider(self) -> LlmProviderName:
        return self._provider

    def active_model(self, provider: LlmProviderName | None = None) -> str:
        return self._active_models[provider or self._provider]

    def api_key(self, provider: LlmProviderName | None = None) -> str | None:
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
        if spec is None or model not in self._effective_models(spec.name):
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
        spec = self._require_external_provider(provider)
        self._apply_change(
            actor_user_id,
            actor_username,
            "ai_api_key_configured",
            {"provider": spec.name},
            lambda: self._api_keys.__setitem__(spec.name, api_key),
        )
        return self.state()

    def refresh_models(
        self, actor_user_id: str, actor_username: str, provider: str
    ) -> AiModelState:
        """Append safe live discoveries without removing existing model IDs."""
        spec = self._require_refreshable_provider(provider)
        key = self._api_keys.get(spec.name)
        if not key:
            raise AppError(
                409,
                "provider_not_configured",
                "Save an API key for this provider before refreshing its models.",
            )
        discovered = discover_models(spec.name, key, self._settings.llm_api_timeout_seconds)
        current = self._discovered_models[spec.name]
        existing = {*spec.models, *self._custom_models[spec.name], *current}
        candidates = [model for model in clean_model_ids(discovered) if model not in existing]
        additions = candidates[: MAX_MODELS_PER_SOURCE - len(current)]
        merged = [*current, *additions]
        self._apply_change(
            actor_user_id,
            actor_username,
            "ai_models_refreshed",
            {
                "provider": spec.name,
                "returned": str(len(discovered)),
                "added": str(len(additions)),
            },
            lambda: self._discovered_models.__setitem__(spec.name, merged),
            record_actor=False,
        )
        return self.state()

    def add_custom_model(
        self, actor_user_id: str, actor_username: str, provider: str, model: str
    ) -> AiModelState:
        """Register a model ID without changing the provider's active model."""
        spec = self._require_external_provider(provider)
        model = model.strip()
        if not is_valid_model_id(model):
            raise AppError(422, "invalid_model_id", "The model ID contains unsupported characters.")
        if model in self._effective_models(spec.name):
            return self.state()
        if len(self._custom_models[spec.name]) >= MAX_MODELS_PER_SOURCE:
            raise AppError(409, "model_limit_reached", "The custom model limit has been reached.")
        self._apply_change(
            actor_user_id,
            actor_username,
            "ai_custom_model_added",
            {"provider": spec.name, "model": model},
            lambda: self._custom_models[spec.name].append(model),
        )
        return self.state()

    def _require_external_provider(self, provider: str) -> ProviderSpec:
        spec = self._spec(provider)
        if spec is None or spec.name == "mock":
            raise AppError(
                422, "provider_not_available", "The requested provider is not available."
            )
        return spec

    def _require_refreshable_provider(self, provider: str) -> ProviderSpec:
        spec = self._require_external_provider(provider)
        if not spec.supports_model_refresh:
            raise AppError(
                422,
                "refresh_not_supported",
                "Live model listing is not available for this provider. "
                "Add model IDs by hand instead.",
            )
        return spec

    def _apply_change(
        self,
        actor_user_id: str,
        actor_username: str,
        event_type: str,
        metadata: dict[str, str],
        mutate: Callable[[], None],
        record_actor: bool = True,
    ) -> None:
        snapshot = self._snapshot()
        try:
            mutate()
            if record_actor:
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
        restored = restore_model_state(payload, provider_specs(self._settings))
        self._active_models = restored.active_models
        self._custom_models = restored.custom_models
        self._discovered_models = restored.discovered_models
        self._changed_by = restored.changed_by
        self._changed_at = restored.changed_at
        # Re-save to scrub legacy keys and invalid or oversized model IDs.
        self._persist()

    def _persist(self) -> None:
        if self._state_store is None:
            return
        self._state_store.save(
            AI_MODEL_NAMESPACE,
            model_state_payload(
                active_provider=self._provider,
                active_models=self._active_models,
                custom_models=self._custom_models,
                discovered_models=self._discovered_models,
                changed_by=self._changed_by,
                changed_at=self._changed_at,
            ),
        )

    def _snapshot(self) -> _AiModelSnapshot:
        return _AiModelSnapshot(
            provider=self._provider,
            active_models=dict(self._active_models),
            custom_models={name: list(models) for name, models in self._custom_models.items()},
            discovered_models={
                name: list(models) for name, models in self._discovered_models.items()
            },
            api_keys=dict(self._api_keys),
            changed_by=self._changed_by,
            changed_at=self._changed_at,
        )

    def _restore(self, snapshot: _AiModelSnapshot) -> None:
        self._provider = snapshot.provider
        self._active_models = dict(snapshot.active_models)
        self._custom_models = {
            name: list(models) for name, models in snapshot.custom_models.items()
        }
        self._discovered_models = {
            name: list(models) for name, models in snapshot.discovered_models.items()
        }
        self._api_keys = dict(snapshot.api_keys)
        self._changed_by = snapshot.changed_by
        self._changed_at = snapshot.changed_at
