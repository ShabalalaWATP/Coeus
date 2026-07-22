from uuid import uuid4

import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.persistence.state_store import MemoryStateStore
from coeus.services.audit import AuditLog
from coeus.services.integration_secrets import (
    EncryptedIntegrationSecretStore,
    integration_secret_namespace,
)
from coeus.services.search_configuration import (
    SEARCH_CONFIGURATION_NAMESPACE,
    SEARCH_EMBEDDING_DIMENSIONS,
    SEARCH_GEMINI_CREDENTIAL_NAME,
    SearchConfigurationService,
)
from coeus.services.search_configuration_codec import (
    encode_datetime,
    optional_datetime,
    optional_string,
    search_index_status,
)


def _service(
    state: MemoryStateStore | None = None,
    audit: AuditLog | None = None,
) -> tuple[SearchConfigurationService, MemoryStateStore]:
    state = state or MemoryStateStore()
    settings = Settings(environment="test")
    return (
        SearchConfigurationService(
            settings,
            audit or AuditLog(),
            state,
            EncryptedIntegrationSecretStore(state, settings),
        ),
        state,
    )


def test_search_configuration_is_separate_and_persists_encrypted_key() -> None:
    service, state = _service()
    assert service.state().provider == "mock"
    assert service.state().model == "token-hash-v2"
    assert service.state().dimensions == SEARCH_EMBEDDING_DIMENSIONS
    assert service.state().evaluation_status == "approved"
    assert service.state().definitive_no_match_enabled is True

    service.configure_key("admin-id", "admin@example.test", "search-secret-value")
    encrypted = state.load(integration_secret_namespace(SEARCH_GEMINI_CREDENTIAL_NAME))
    assert encrypted is not None
    assert "search-secret-value" not in str(encrypted)

    restarted, _ = _service(state)
    assert restarted.api_key() == "search-secret-value"
    assert restarted.state().api_key_configured is True
    assert restarted.state().changed_by == "admin@example.test"


def test_external_provider_requires_key_and_explicit_egress_confirmation() -> None:
    service, _ = _service()
    with pytest.raises(AppError, match="Save a search API key"):
        service.configure("1", "admin", "gemini_api", "gemini-embedding-2", True)

    service.configure_key("1", "admin", "search-secret-value")
    with pytest.raises(AppError, match="Confirm that synthetic search text"):
        service.configure("1", "admin", "gemini_api", "gemini-embedding-2", False)

    state = service.configure("1", "admin", "gemini_api", "gemini-embedding-2", True)
    assert state.provider == "gemini_api"
    assert state.model == "gemini-embedding-2"
    assert state.index_status == "stale"
    assert state.evaluation_status == "required"
    assert state.definitive_no_match_enabled is False


def test_deployment_can_allowlist_an_evaluated_gemini_search_release() -> None:
    store = MemoryStateStore()
    settings = Settings(
        environment="test",
        embedding_provider="gemini_api",
        gemini_api_key="synthetic-search-key",
        search_approved_releases=["gemini_api:gemini-embedding-2:1536"],
    )
    service = SearchConfigurationService(
        settings,
        AuditLog(),
        store,
        EncryptedIntegrationSecretStore(store, settings),
    )

    assert service.state().evaluation_status == "approved"
    assert service.state().definitive_no_match_enabled is True


def test_reindex_generation_is_single_flight_and_reusable() -> None:
    service, _ = _service()
    first = service.mark_indexing(str(uuid4()))
    assert first.index_generation == 1
    with pytest.raises(AppError, match="already running"):
        service.mark_indexing(str(uuid4()))
    with pytest.raises(AppError, match="cannot change"):
        service.configure("1", "admin", "mock", "token-hash-v2", False)

    service.mark_ready("1")
    second = service.mark_indexing("1")
    assert second.index_generation == 2
    assert second.space_id != first.space_id


def test_configuration_and_secret_roll_back_when_audit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = AuditLog()
    service, state = _service(audit=audit)

    def fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(audit, "record", fail)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.configure_key("1", "admin", "search-secret-value")

    assert service.api_key() is None
    assert state.load(integration_secret_namespace(SEARCH_GEMINI_CREDENTIAL_NAME)) == {}
    assert state.load(SEARCH_CONFIGURATION_NAMESPACE)["changed_by"] is None


def test_index_state_rolls_back_when_audit_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    audit = AuditLog()
    service, state = _service(audit=audit)
    before = state.load(SEARCH_CONFIGURATION_NAMESPACE)

    monkeypatch.setattr(
        audit,
        "record",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("audit unavailable")),
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.mark_indexing("1")

    assert service.state().index_status == "stale"
    assert state.load(SEARCH_CONFIGURATION_NAMESPACE) == before


def test_configuration_rejects_invalid_provider_model_and_short_key() -> None:
    service, _ = _service()

    with pytest.raises(AppError, match="API key is not valid"):
        service.configure_key("1", "admin", "short")
    with pytest.raises(AppError, match="provider is not available"):
        service.configure("1", "admin", "unknown", "model", False)
    with pytest.raises(AppError, match="model is not available"):
        service.configure("1", "admin", "mock", "unknown", False)

    unchanged = service.configure("1", "admin", "mock", "token-hash-v2", False)
    assert unchanged.provider == "mock"


def test_environment_key_cannot_be_replaced() -> None:
    state = MemoryStateStore()
    settings = Settings(environment="test", gemini_api_key="environment-search-key")
    service = SearchConfigurationService(
        settings,
        AuditLog(),
        state,
        EncryptedIntegrationSecretStore(state, settings),
    )

    assert service.api_key() == "environment-search-key"
    with pytest.raises(AppError, match="managed by the environment"):
        service.configure_key("1", "admin", "replacement-key")


def test_ready_state_becomes_stale_when_the_corpus_changes() -> None:
    service, _ = _service()
    service.set_index_counts_provider(lambda: (2, 4, 3, 1, "corpus-v1"))
    service.set_current_corpus_version_provider(lambda: "corpus-v1")
    service.mark_indexing("1")
    ready = service.mark_ready("1")
    assert ready.index_status == "ready"
    assert ready.failed_asset_count == 1

    service.set_current_corpus_version_provider(lambda: "corpus-v2")
    stale = service.state()
    assert stale.index_status == "stale"
    assert stale.degraded_reason == "corpus_changed"


def test_failure_reason_is_allowlisted_and_previous_key_is_restored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = AuditLog()
    service, state = _service(audit=audit)
    service.configure_key("1", "admin", "existing-search-key")

    monkeypatch.setattr(
        audit,
        "record",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("audit unavailable")),
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.configure_key("1", "admin", "replacement-search-key")

    restarted, _ = _service(state)
    assert restarted.api_key() == "existing-search-key"
    failed = restarted.mark_failed("1", "unsafe implementation detail")
    assert failed.index_status == "failed"
    assert failed.degraded_reason == "failed"


def test_invalid_persisted_configuration_is_replaced_with_safe_defaults() -> None:
    invalid_provider = MemoryStateStore()
    invalid_provider.save(
        SEARCH_CONFIGURATION_NAMESPACE,
        {"provider": "unknown", "model": "unknown"},
    )
    service, state = _service(invalid_provider)
    assert service.state().provider == "mock"
    assert state.load(SEARCH_CONFIGURATION_NAMESPACE)["provider"] == "mock"

    invalid_model = MemoryStateStore()
    invalid_model.save(
        SEARCH_CONFIGURATION_NAMESPACE,
        {"provider": "mock", "model": "unknown"},
    )
    service, state = _service(invalid_model)
    assert service.state().model == "token-hash-v2"
    assert state.load(SEARCH_CONFIGURATION_NAMESPACE)["model"] == "token-hash-v2"


def test_search_configuration_scalar_codecs_reject_malformed_values() -> None:
    assert search_index_status("ready") == "ready"
    assert search_index_status("unknown") == "stale"
    assert optional_string("value") == "value"
    assert optional_string(0) is None
    assert optional_datetime(None) is None
    assert optional_datetime("not-a-date") is None
    timestamp = optional_datetime("2026-07-17T12:00:00+00:00")
    assert timestamp is not None
    assert encode_datetime(timestamp) == "2026-07-17T12:00:00+00:00"
    assert encode_datetime(None) is None
