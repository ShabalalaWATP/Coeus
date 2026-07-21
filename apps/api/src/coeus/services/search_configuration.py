"""Persisted administration state for retrieval embeddings and index health."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal, cast

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.core.logging import get_logger
from coeus.domain.search_index import SEARCH_EMBEDDING_DIMENSIONS
from coeus.persistence.state_store import StateStore
from coeus.services import search_configuration_codec as codec
from coeus.services.audit import AuditLog
from coeus.services.integration_secrets import EncryptedIntegrationSecretStore

SEARCH_CONFIGURATION_NAMESPACE = "search_configuration"
SEARCH_GEMINI_CREDENTIAL_NAME = "search_embedding:gemini_api"
SearchProvider = Literal["mock", "gemini_api"]
PROVIDER_MODELS: dict[SearchProvider, tuple[str, ...]] = {
    "mock": ("token-hash-v2",),
    "gemini_api": ("gemini-embedding-2",),
}
_SAFE_FAILURE_REASONS = frozenset({"corpus_changed", "provider_unavailable", "index_write_failed"})
logger = get_logger(__name__)


@dataclass(frozen=True)
class SearchConfigurationState:
    provider: SearchProvider
    model: str
    dimensions: int
    api_key_configured: bool
    available_providers: tuple[SearchProvider, ...]
    available_models: tuple[str, ...]
    index_status: codec.SearchIndexStatus
    index_generation: int
    product_count: int
    chunk_count: int
    ticket_count: int
    failed_asset_count: int
    corpus_version: str
    changed_by: str | None
    changed_at: datetime | None
    last_indexed_at: datetime | None
    degraded_reason: str | None
    release_id: str
    evaluation_status: str
    definitive_no_match_enabled: bool

    @property
    def space_id(self) -> str:
        return f"{self.provider}:{self.model}:{self.dimensions}:g{self.index_generation}"


class SearchConfigurationService:
    """Own the search provider independently of chat and voice providers."""

    def __init__(
        self,
        settings: Settings,
        audit_log: AuditLog,
        state_store: StateStore,
        secret_store: EncryptedIntegrationSecretStore,
    ) -> None:
        self._settings = settings
        self._audit_log = audit_log
        self._state_store = state_store
        self._secret_store = secret_store
        self._environment_key = settings.gemini_api_key
        self._persisted_key = (
            None if self._environment_key else secret_store.load(SEARCH_GEMINI_CREDENTIAL_NAME)
        )
        default_provider: SearchProvider = (
            "gemini_api" if settings.embedding_provider == "gemini_api" else "mock"
        )
        default_model = PROVIDER_MODELS[default_provider][0]
        self._state = SearchConfigurationState(
            provider=default_provider,
            model=default_model,
            dimensions=SEARCH_EMBEDDING_DIMENSIONS,
            api_key_configured=bool(self.api_key()),
            available_providers=tuple(PROVIDER_MODELS),
            available_models=PROVIDER_MODELS[default_provider],
            index_status="stale",
            index_generation=1,
            product_count=0,
            chunk_count=0,
            ticket_count=0,
            failed_asset_count=0,
            corpus_version="unindexed",
            changed_by=None,
            changed_at=None,
            last_indexed_at=None,
            degraded_reason=None,
            release_id=f"{default_provider}:{default_model}:{SEARCH_EMBEDDING_DIMENSIONS}",
            evaluation_status="required",
            definitive_no_match_enabled=False,
        )
        self._index_counts: Callable[[], tuple[int, int, int, int, str]] = lambda: (
            0,
            0,
            0,
            0,
            "unindexed",
        )
        self._current_corpus_version: Callable[[], str] = lambda: "unindexed"
        self._restore_or_persist()

    def state(self) -> SearchConfigurationState:
        products, chunks, tickets, failed_assets, corpus_version = self._index_counts()
        index_status = self._state.index_status
        degraded_reason = self._state.degraded_reason
        if (
            index_status == "ready"
            and corpus_version != "unindexed"
            and self._current_corpus_version() != corpus_version
        ):
            index_status = "stale"
            degraded_reason = "corpus_changed"
        release_id = f"{self._state.provider}:{self._state.model}:{self._state.dimensions}"
        approved = release_id in self._settings.search_approved_releases
        return replace(
            self._state,
            api_key_configured=bool(self.api_key()),
            product_count=products,
            chunk_count=chunks,
            ticket_count=tickets,
            failed_asset_count=failed_assets,
            corpus_version=corpus_version,
            index_status=index_status,
            degraded_reason=degraded_reason,
            release_id=release_id,
            evaluation_status="approved" if approved else "required",
            definitive_no_match_enabled=approved,
        )

    def api_key(self) -> str | None:
        return self._environment_key or self._persisted_key

    def set_index_counts_provider(
        self, provider: Callable[[], tuple[int, int, int, int, str]]
    ) -> None:
        self._index_counts = provider

    def set_current_corpus_version_provider(self, provider: Callable[[], str]) -> None:
        self._current_corpus_version = provider

    def configure_key(self, actor_id: str, actor_username: str, api_key: str) -> None:
        if self._environment_key:
            raise AppError(
                409,
                "search_key_managed_by_environment",
                "The search embedding key is managed by the environment.",
            )
        value = api_key.strip()
        if len(value) < 10:
            raise AppError(422, "invalid_api_key", "The API key is not valid.")
        previous_key = self._persisted_key
        previous_state = self._state
        try:
            self._secret_store.save(SEARCH_GEMINI_CREDENTIAL_NAME, value)
            self._persisted_key = value
            self._state = replace(
                self._state,
                changed_by=actor_username,
                changed_at=datetime.now(UTC),
            )
            self._persist()
            self._audit_log.record(
                "search_embedding_key_configured", actor_id, {"provider": "gemini_api"}
            )
        except Exception:
            self._state = previous_state
            self._persisted_key = previous_key
            self._restore_key(previous_key)
            self._restore_persisted_state()
            raise

    def configure(
        self,
        actor_id: str,
        actor_username: str,
        provider: str,
        model: str,
        confirm_external_egress: bool,
    ) -> SearchConfigurationState:
        if self._state.index_status == "indexing":
            raise AppError(
                409,
                "search_reindex_active",
                "Search configuration cannot change during a re-index.",
            )
        if provider not in PROVIDER_MODELS:
            raise AppError(422, "provider_not_available", "Search provider is not available.")
        typed_provider: SearchProvider = provider
        if model not in PROVIDER_MODELS[typed_provider]:
            raise AppError(422, "model_not_available", "Search model is not available.")
        if typed_provider == "gemini_api":
            if not self.api_key():
                raise AppError(422, "provider_not_configured", "Save a search API key first.")
            if not confirm_external_egress:
                raise AppError(
                    422,
                    "external_egress_not_confirmed",
                    "Confirm that synthetic search text may be sent to Gemini.",
                )
        if typed_provider == self._state.provider and model == self._state.model:
            return self.state()
        next_state = replace(
            self._state,
            provider=typed_provider,
            model=model,
            available_models=PROVIDER_MODELS[typed_provider],
            index_generation=self._state.index_generation + 1,
            index_status="stale",
            changed_by=actor_username,
            changed_at=datetime.now(UTC),
            degraded_reason=None,
        )
        self._apply_state_change(
            next_state,
            "search_embedding_configuration_changed",
            actor_id,
            {
                "provider": typed_provider,
                "model": model,
                "generation": str(next_state.index_generation),
            },
        )
        return self.state()

    def mark_indexing(self, actor_id: str) -> SearchConfigurationState:
        if self._state.index_status == "indexing":
            raise AppError(409, "search_reindex_active", "A search re-index is already running.")
        generation = self._state.index_generation
        if self._state.index_status in {"ready", "failed", "degraded"}:
            generation += 1
        next_state = replace(
            self._state,
            index_status="indexing",
            index_generation=generation,
            degraded_reason=None,
        )
        self._apply_state_change(
            next_state,
            "search_reindex_started",
            actor_id,
            {"space_id": next_state.space_id},
        )
        return self.state()

    def mark_ready(self, actor_id: str) -> SearchConfigurationState:
        next_state = replace(
            self._state,
            index_status="ready",
            degraded_reason=None,
            last_indexed_at=datetime.now(UTC),
        )
        self._apply_state_change(
            next_state,
            "search_reindex_completed",
            actor_id,
            {"space_id": next_state.space_id},
        )
        return self.state()

    def mark_failed(self, actor_id: str, reason: str) -> SearchConfigurationState:
        safe_reason = reason if reason in _SAFE_FAILURE_REASONS else "failed"
        next_state = replace(self._state, index_status="failed", degraded_reason=safe_reason)
        self._apply_state_change(
            next_state,
            "search_reindex_failed",
            actor_id,
            {"space_id": next_state.space_id, "reason": safe_reason},
        )
        return self.state()

    def _apply_state_change(
        self,
        next_state: SearchConfigurationState,
        event_type: str,
        actor_id: str,
        detail: dict[str, str],
    ) -> None:
        previous = self._state
        self._state = next_state
        try:
            self._persist()
            self._audit_log.record(event_type, actor_id, detail)
        except Exception:
            self._state = previous
            self._restore_persisted_state()
            raise

    def _restore_key(self, previous: str | None) -> None:
        if previous:
            self._secret_store.save(SEARCH_GEMINI_CREDENTIAL_NAME, previous)
        else:
            self._secret_store.clear(SEARCH_GEMINI_CREDENTIAL_NAME)

    def _restore_persisted_state(self) -> None:
        try:
            self._persist()
        except Exception:
            logger.exception("search_configuration_rollback_persist_failed")

    def _restore_or_persist(self) -> None:
        payload = self._state_store.load(SEARCH_CONFIGURATION_NAMESPACE)
        if payload is None:
            self._persist()
            return
        provider = payload.get("provider")
        model = payload.get("model")
        if provider not in PROVIDER_MODELS:
            self._persist()
            return
        typed_provider = cast(SearchProvider, provider)
        if model not in PROVIDER_MODELS[typed_provider]:
            self._persist()
            return
        self._state = replace(
            self._state,
            provider=typed_provider,
            model=str(model),
            available_models=PROVIDER_MODELS[typed_provider],
            index_status=codec.search_index_status(payload.get("index_status")),
            index_generation=max(1, int(payload.get("index_generation", 1))),
            changed_by=codec.optional_string(payload.get("changed_by")),
            changed_at=codec.optional_datetime(payload.get("changed_at")),
            last_indexed_at=codec.optional_datetime(payload.get("last_indexed_at")),
            degraded_reason=codec.optional_string(payload.get("degraded_reason")),
        )
        self._persist()

    def _persist(self) -> None:
        self._state_store.save(
            SEARCH_CONFIGURATION_NAMESPACE,
            {
                "provider": self._state.provider,
                "model": self._state.model,
                "dimensions": self._state.dimensions,
                "index_status": self._state.index_status,
                "index_generation": self._state.index_generation,
                "changed_by": self._state.changed_by,
                "changed_at": codec.encode_datetime(self._state.changed_at),
                "last_indexed_at": codec.encode_datetime(self._state.last_indexed_at),
                "degraded_reason": self._state.degraded_reason,
            },
        )
