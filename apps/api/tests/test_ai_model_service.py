"""AiModelService unit tests: persistence, rollbacks and key handling."""

import pytest

from ai_model_helpers import FailingAuditLog
from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.core.model_ids import MAX_MODELS_PER_SOURCE
from coeus.persistence.state_store import MemoryStateStore
from coeus.services.ai_models import AI_MODEL_NAMESPACE, AiModelService
from coeus.services.ai_provider_catalog import ProviderSpec
from coeus.services.audit import AuditLog
from coeus.services.integration_secrets import integration_secret_namespace


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


def test_admin_api_keys_are_encrypted_and_restored_with_the_active_provider() -> None:
    state_store = MemoryStateStore()
    settings = Settings(environment="test")
    service = AiModelService(settings, AuditLog(), state_store=state_store)

    payload = state_store.load(AI_MODEL_NAMESPACE)
    assert payload is not None
    assert "api_key" not in payload
    service.configure_api_key("admin-id", "admin@example.test", "runtime-secret")
    service.configure_api_key("admin-id", "admin@example.test", "sk-runtime", "openai_api")
    service.select("admin-id", "admin@example.test", "gpt-5.6-sol", "openai_api")
    service.select_provider("admin-id", "admin@example.test", "openai_api")

    payload = state_store.load(AI_MODEL_NAMESPACE)
    assert payload is not None
    gemini_envelope = state_store.load(integration_secret_namespace("llm:gemini_api"))
    openai_envelope = state_store.load(integration_secret_namespace("llm:openai_api"))
    assert gemini_envelope and openai_envelope
    assert "runtime-secret" not in str(payload)
    assert "sk-runtime" not in str(payload)
    assert "runtime-secret" not in str(gemini_envelope)
    assert "sk-runtime" not in str(openai_envelope)

    restarted = AiModelService(settings, AuditLog(), state_store)
    assert restarted.api_key("gemini_api") == "runtime-secret"
    assert restarted.api_key("openai_api") == "sk-runtime"
    assert restarted.provider() == "openai_api"
    assert restarted.active_model() == "gpt-5.6-sol"


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
    assert service.active_model("gemini_api") == "gemini-3.5-flash"
    assert "api_key" not in payload
    assert "legacy-secret" not in str(payload)


def test_environment_api_key_is_authoritative_and_not_copied_to_state() -> None:
    state_store = MemoryStateStore()
    service = AiModelService(
        Settings(environment="test", gemini_api_key="env-secret"), AuditLog(), state_store
    )

    with pytest.raises(AppError, match="managed by the environment"):
        service.configure_api_key("admin-id", "admin@example.test", "replacement")

    assert service.api_key("gemini_api") == "env-secret"
    envelope = state_store.load(integration_secret_namespace("llm:gemini_api"))
    assert envelope == {}
    assert "env-secret" not in str(state_store.load(AI_MODEL_NAMESPACE))


def test_legacy_gemini_catalogue_additions_are_pruned() -> None:
    state_store = MemoryStateStore()
    state_store.save(
        AI_MODEL_NAMESPACE,
        {
            "active_models": {"gemini_api": "gemini-2.5-pro"},
            "custom_models": {"gemini_api": ["gemini-2.5-pro"]},
            "discovered_models": {"gemini_api": ["gemini-3-flash-preview"]},
        },
    )

    service = AiModelService(Settings(environment="test"), AuditLog(), state_store)
    gemini = next(
        provider for provider in service.state().providers if provider.name == "gemini_api"
    )

    assert gemini.models == (
        "gemini-3.5-flash",
        "gemini-3.1-pro-preview",
        "gemma-4-31b-it",
        "gemma-4-26b-a4b-it",
    )
    assert gemini.active_model == "gemini-3.5-flash"


def test_selecting_active_model_is_a_noop() -> None:
    audit_log = AuditLog()
    service = AiModelService(Settings(environment="test"), audit_log, MemoryStateStore())

    state = service.select("admin-id", "admin@example.test", "gemini-3.5-flash", "gemini_api")

    assert state.changed_by is None
    assert service.active_model("gemini_api") == "gemini-3.5-flash"
    assert audit_log.list_events() == ()


def test_model_selection_rolls_back_when_audit_fails() -> None:
    state_store = MemoryStateStore()
    service = AiModelService(Settings(environment="test"), FailingAuditLog(), state_store)

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.select("admin-id", "admin@example.test", "gemini-3.1-pro-preview", "gemini_api")

    payload = state_store.load(AI_MODEL_NAMESPACE)
    assert payload is not None
    assert service.active_model("gemini_api") == "gemini-3.5-flash"
    assert service.state().changed_by is None
    assert payload["active_models"]["gemini_api"] == "gemini-3.5-flash"


def test_model_selection_rolls_back_when_persistence_fails() -> None:
    state_store = ToggleStateStore()
    service = AiModelService(Settings(environment="test"), AuditLog(), state_store)

    state_store.fail_saves = True
    with pytest.raises(RuntimeError, match="state store unavailable"):
        service.select("admin-id", "admin@example.test", "gemini-3.1-pro-preview", "gemini_api")

    assert service.active_model("gemini_api") == "gemini-3.5-flash"
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

    service.select("admin-id", "admin@example.test", "gpt-5.6-sol", "openai_api")
    service.select_provider("admin-id", "admin@example.test", "openai_api")
    assert service.provider() == "openai_api"
    assert service.active_model() == "gpt-5.6-sol"

    # A restart restores both the provider and its model choice.
    restarted = AiModelService(settings, AuditLog(), state_store)
    assert restarted.active_model("openai_api") == "gpt-5.6-sol"
    assert restarted.provider() == "openai_api"


def test_key_configuration_rejects_the_mock_provider() -> None:
    service = AiModelService(Settings(environment="test"), AuditLog(), MemoryStateStore())

    with pytest.raises(AppError, match="not available"):
        service.configure_api_key("admin-id", "admin@example.test", "runtime-secret", "mock")


def test_custom_models_persist_without_becoming_active() -> None:
    state_store = MemoryStateStore()
    settings = Settings(environment="test")
    service = AiModelService(settings, AuditLog(), state_store)

    custom = "anthropic.claude-opus-5-20261101-v1:0"
    service.add_custom_model("admin-id", "admin@example.test", "bedrock", custom)

    restarted = AiModelService(settings, AuditLog(), state_store)
    bedrock = next(p for p in restarted.state().providers if p.name == "bedrock")
    assert custom in bedrock.models

    service.select("admin-id", "admin@example.test", custom, "bedrock")
    selected = AiModelService(settings, AuditLog(), state_store)
    assert selected.active_model("bedrock") == custom


def test_curated_openai_catalogue_rejects_refresh_and_custom_models() -> None:
    service = AiModelService(
        Settings(environment="test", openai_api_key="sk-env"), AuditLog(), MemoryStateStore()
    )
    with pytest.raises(AppError, match="Live model listing is not available"):
        service.refresh_models("admin-id", "admin@example.test", "openai_api")
    with pytest.raises(AppError, match="catalogue is curated"):
        service.add_custom_model("admin-id", "admin@example.test", "openai_api", "gpt-old")


def test_effective_models_are_empty_for_an_unknown_provider() -> None:
    service = AiModelService(Settings(environment="test"), AuditLog(), MemoryStateStore())

    assert service._effective_models("unknown") == ()


def test_refresh_requires_a_key_and_preserves_the_actor_for_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from coeus.services import ai_models as ai_models_module

    original_spec_for = ai_models_module.spec_for
    refreshable = ProviderSpec(
        name="vertex_ai",
        label="GCP Vertex AI",
        models=("vertex-existing",),
        default_model="vertex-existing",
        supports_model_refresh=True,
    )
    monkeypatch.setattr(
        ai_models_module,
        "spec_for",
        lambda settings, name: (
            refreshable if name == "vertex_ai" else original_spec_for(settings, name)
        ),
    )
    no_key = AiModelService(Settings(environment="test"), AuditLog(), MemoryStateStore())
    with pytest.raises(AppError, match="Save an API key"):
        no_key.refresh_models("admin-id", "admin@example.test", "vertex_ai")

    configured = AiModelService(
        Settings(environment="test", vertex_api_key="vertex-key"),
        AuditLog(),
        MemoryStateStore(),
        model_discovery=lambda *_args: ["vertex-new"],
    )
    state = configured.refresh_models("admin-id", "admin@example.test", "vertex_ai")
    vertex = next(provider for provider in state.providers if provider.name == "vertex_ai")

    assert "vertex-new" in vertex.models
    assert state.changed_by is None


def test_custom_model_validation_and_capacity_are_enforced() -> None:
    service = AiModelService(Settings(environment="test"), AuditLog(), MemoryStateStore())
    with pytest.raises(AppError, match="unsupported characters"):
        service.add_custom_model("admin-id", "admin@example.test", "bedrock", "bad id")

    state_store = MemoryStateStore()
    state_store.save(
        AI_MODEL_NAMESPACE,
        {
            "custom_models": {
                "bedrock": [f"custom-{index}" for index in range(MAX_MODELS_PER_SOURCE)]
            }
        },
    )
    at_capacity = AiModelService(Settings(environment="test"), AuditLog(), state_store)
    with pytest.raises(AppError, match="limit"):
        at_capacity.add_custom_model("admin-id", "admin@example.test", "bedrock", "one-more")


def test_persisted_model_ids_are_sanitised_and_bounded() -> None:
    state_store = MemoryStateStore()
    candidates = [f"bedrock-custom-{index}" for index in range(MAX_MODELS_PER_SOURCE + 25)]
    state_store.save(
        AI_MODEL_NAMESPACE,
        {
            "custom_models": {"bedrock": [*candidates, "bad id", "x" * 81]},
            "active_models": {"bedrock": "bad id"},
        },
    )

    service = AiModelService(Settings(environment="test"), AuditLog(), state_store)
    bedrock = next(provider for provider in service.state().providers if provider.name == "bedrock")
    extras = [model for model in bedrock.models if model.startswith("bedrock-custom-")]

    assert len(extras) == MAX_MODELS_PER_SOURCE
    assert "bad id" not in bedrock.models
    assert "x" * 81 not in bedrock.models
