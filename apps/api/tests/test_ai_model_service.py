"""AiModelService unit tests: persistence, rollbacks and key handling."""

import pytest

from ai_model_helpers import FailingAuditLog
from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.core.model_ids import MAX_MODELS_PER_SOURCE
from coeus.persistence.state_store import MemoryStateStore
from coeus.services.ai_models import AI_MODEL_NAMESPACE, AiModelService
from coeus.services.audit import AuditLog


class ToggleStateStore:
    def __init__(self) -> None:
        self.fail_saves = False
        self.payloads: dict[str, dict[str, object]] = {}

    def load(self, namespace: str) -> dict[str, object] | None:
        return self.payloads.get(namespace)

    def save(self, namespace: str, payload: dict[str, object]) -> None:
        if self.fail_saves:
            raise RuntimeError("state store unavailable")
        self.payloads[namespace] = payload


def test_api_keys_are_not_persisted_in_state_store() -> None:
    state_store = MemoryStateStore()
    service = AiModelService(
        Settings(environment="test", gemini_api_key="env-secret"),
        AuditLog(),
        state_store=state_store,
    )

    payload = state_store.load(AI_MODEL_NAMESPACE)
    assert payload is not None
    assert "api_key" not in payload
    assert "env-secret" not in str(payload)

    service.configure_api_key("admin-id", "admin@example.test", "runtime-secret")
    service.configure_api_key("admin-id", "admin@example.test", "sk-runtime", "openai_api")

    payload = state_store.load(AI_MODEL_NAMESPACE)
    assert payload is not None
    assert service.api_key("gemini_api") == "runtime-secret"
    assert service.api_key("openai_api") == "sk-runtime"
    assert "runtime-secret" not in str(payload)
    assert "sk-runtime" not in str(payload)


def test_legacy_persisted_gemini_key_is_scrubbed() -> None:
    state_store = MemoryStateStore()
    state_store.save(
        AI_MODEL_NAMESPACE,
        {"active_model": "gemini-2.5-pro", "api_key": "legacy-secret"},
    )

    service = AiModelService(Settings(environment="test"), AuditLog(), state_store=state_store)

    payload = state_store.load(AI_MODEL_NAMESPACE)
    assert payload is not None
    assert service.api_key("gemini_api") is None
    assert service.active_model("gemini_api") == "gemini-2.5-pro"
    assert "api_key" not in payload
    assert "legacy-secret" not in str(payload)


def test_selecting_active_model_is_a_noop() -> None:
    audit_log = AuditLog()
    service = AiModelService(Settings(environment="test"), audit_log, MemoryStateStore())

    state = service.select("admin-id", "admin@example.test", "gemini-2.5-flash", "gemini_api")

    assert state.changed_by is None
    assert service.active_model("gemini_api") == "gemini-2.5-flash"
    assert audit_log.list_events() == ()


def test_model_selection_rolls_back_when_audit_fails() -> None:
    state_store = MemoryStateStore()
    service = AiModelService(Settings(environment="test"), FailingAuditLog(), state_store)

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.select("admin-id", "admin@example.test", "gemini-2.5-pro", "gemini_api")

    payload = state_store.load(AI_MODEL_NAMESPACE)
    assert payload is not None
    assert service.active_model("gemini_api") == "gemini-2.5-flash"
    assert service.state().changed_by is None
    assert payload["active_models"]["gemini_api"] == "gemini-2.5-flash"


def test_model_selection_rolls_back_when_persistence_fails() -> None:
    state_store = ToggleStateStore()
    service = AiModelService(Settings(environment="test"), AuditLog(), state_store)

    state_store.fail_saves = True
    with pytest.raises(RuntimeError, match="state store unavailable"):
        service.select("admin-id", "admin@example.test", "gemini-2.5-pro", "gemini_api")

    assert service.active_model("gemini_api") == "gemini-2.5-flash"
    assert service.state().changed_by is None


def test_api_key_configuration_rolls_back_when_audit_fails() -> None:
    state_store = MemoryStateStore()
    service = AiModelService(Settings(environment="test"), FailingAuditLog(), state_store)

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.configure_api_key("admin-id", "admin@example.test", "runtime-secret")

    payload = state_store.load(AI_MODEL_NAMESPACE)
    assert payload is not None
    assert service.provider() == "mock"
    assert service.api_key("gemini_api") is None
    assert "runtime-secret" not in str(payload)


def test_provider_switch_rolls_back_when_audit_fails() -> None:
    state_store = MemoryStateStore()
    service = AiModelService(
        Settings(environment="test", openai_api_key="sk-env"), FailingAuditLog(), state_store
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.select_provider("admin-id", "admin@example.test", "openai_api")

    assert service.provider() == "mock"
    assert service.state().changed_by is None


def test_env_configured_provider_can_be_activated_and_restored_models_apply() -> None:
    state_store = MemoryStateStore()
    settings = Settings(environment="test", openai_api_key="sk-env")
    service = AiModelService(settings, AuditLog(), state_store)

    service.select("admin-id", "admin@example.test", "gpt-5", "openai_api")
    service.select_provider("admin-id", "admin@example.test", "openai_api")
    assert service.provider() == "openai_api"
    assert service.active_model() == "gpt-5"

    # A restart restores per-provider model choices from the state store.
    restarted = AiModelService(settings, AuditLog(), state_store)
    assert restarted.active_model("openai_api") == "gpt-5"
    # The provider itself is runtime-only, like the keys.
    assert restarted.provider() == "mock"


def test_key_configuration_rejects_the_mock_provider() -> None:
    service = AiModelService(Settings(environment="test"), AuditLog(), MemoryStateStore())

    with pytest.raises(AppError, match="not available"):
        service.configure_api_key("admin-id", "admin@example.test", "runtime-secret", "mock")


def test_custom_models_persist_without_becoming_active() -> None:
    state_store = MemoryStateStore()
    settings = Settings(environment="test", openai_api_key="sk-env")
    service = AiModelService(settings, AuditLog(), state_store)

    service.add_custom_model("admin-id", "admin@example.test", "openai_api", "gpt-6-omni")
    assert "gpt-6-omni" in service.state().providers[1].models

    restarted = AiModelService(settings, AuditLog(), state_store)
    openai = next(p for p in restarted.state().providers if p.name == "openai_api")
    assert "gpt-6-omni" in openai.models
    assert openai.active_model == "gpt-5-mini"

    service.select("admin-id", "admin@example.test", "gpt-6-omni", "openai_api")
    selected = AiModelService(settings, AuditLog(), state_store)
    assert selected.active_model("openai_api") == "gpt-6-omni"


def test_refresh_preserves_custom_and_prior_discovered_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter((("gpt-6-first",), ("gpt-6-second",)))
    monkeypatch.setattr("coeus.services.ai_models.discover_models", lambda *_args: next(responses))
    service = AiModelService(
        Settings(environment="test", openai_api_key="sk-env"), AuditLog(), MemoryStateStore()
    )
    service.add_custom_model("admin-id", "admin@example.test", "openai_api", "gpt-custom")
    service.refresh_models("admin-id", "admin@example.test", "openai_api")
    service.select("admin-id", "admin@example.test", "gpt-6-first", "openai_api")

    state = service.refresh_models("admin-id", "admin@example.test", "openai_api")
    openai = next(provider for provider in state.providers if provider.name == "openai_api")

    assert {"gpt-custom", "gpt-6-first", "gpt-6-second"} <= set(openai.models)
    assert openai.active_model == "gpt-6-first"


def test_refresh_limit_never_evicts_prior_discoveries(monkeypatch: pytest.MonkeyPatch) -> None:
    original = tuple(f"gpt-found-{index:03d}" for index in range(MAX_MODELS_PER_SOURCE))
    responses = iter((original, ("gpt-new-after-limit",)))
    monkeypatch.setattr("coeus.services.ai_models.discover_models", lambda *_args: next(responses))
    service = AiModelService(
        Settings(environment="test", openai_api_key="sk-env"), AuditLog(), MemoryStateStore()
    )

    service.refresh_models("admin-id", "admin@example.test", "openai_api")
    state = service.refresh_models("admin-id", "admin@example.test", "openai_api")
    openai = next(provider for provider in state.providers if provider.name == "openai_api")

    assert set(original) <= set(openai.models)
    assert "gpt-new-after-limit" not in openai.models


def test_refresh_rolls_back_extra_models_when_audit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("coeus.services.ai_models.discover_models", lambda *_args: ("gpt-6-omni",))
    state_store = MemoryStateStore()
    service = AiModelService(
        Settings(environment="test", openai_api_key="sk-env"), FailingAuditLog(), state_store
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.refresh_models("admin-id", "admin@example.test", "openai_api")

    openai = next(p for p in service.state().providers if p.name == "openai_api")
    assert "gpt-6-omni" not in openai.models
    assert service.state().changed_by is None


def test_persisted_model_ids_are_sanitised_and_bounded() -> None:
    state_store = MemoryStateStore()
    candidates = [f"gpt-custom-{index}" for index in range(MAX_MODELS_PER_SOURCE + 25)]
    state_store.save(
        AI_MODEL_NAMESPACE,
        {
            "custom_models": {"openai_api": [*candidates, "bad id", "x" * 81, "gpt-custom-1"]},
            "active_models": {"openai_api": "bad id"},
        },
    )

    service = AiModelService(Settings(environment="test"), AuditLog(), state_store)
    openai = next(
        provider for provider in service.state().providers if provider.name == "openai_api"
    )
    extras = [model for model in openai.models if model.startswith("gpt-custom-")]

    assert len(extras) == MAX_MODELS_PER_SOURCE
    assert "bad id" not in openai.models
    assert "x" * 81 not in openai.models
    assert openai.active_model == "gpt-5-mini"
