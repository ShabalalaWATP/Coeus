from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.tickets import IntakeDetails
from coeus.persistence.state_store import MemoryStateStore
from coeus.services.audit import AuditLog
from coeus.services.integration_secrets import integration_secret_namespace
from coeus.services.realtime_intake_prompt import build_realtime_intake_instructions
from coeus.services.voice_admission import VoiceSessionAdmission
from coeus.services.voice_models import (
    VOICE_CREDENTIAL_NAME,
    VOICE_MODEL_NAMESPACE,
    VoiceModelService,
    VoiceModelState,
)
from coeus.services.voice_sessions import VoiceSessionService


class FailingAuditLog(AuditLog):
    def record(self, *_args: object, **_kwargs: object):  # type: ignore[no-untyped-def]
        raise RuntimeError("audit unavailable")


class EnabledVoiceModels:
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def require_enabled(self) -> VoiceModelState:
        return VoiceModelState("gpt-realtime-mini", ("gpt-realtime-mini",), True, True)

    def api_key(self) -> str | None:
        return self._api_key


class UnusedAdmission:
    def acquire(self, *_args: object):  # type: ignore[no-untyped-def]
        raise AssertionError("admission should not be reached")


def test_realtime_prompt_uses_bounded_application_context_and_next_action() -> None:
    intake = IntakeDetails(
        description="Synthetic vessel activity request",
        operational_question="What changed?",
        area_or_region="Synthetic Baltic ports",
        missing_information=("time_period", "priority", "requesting_unit"),
    )

    instructions = build_realtime_intake_instructions(intake)

    assert '"operational_question"' in instructions
    assert "What changed?" not in instructions
    assert '"missing_fields": ["time_period", "priority", "requesting_unit"]' in instructions
    assert "What time period should this cover?" in instructions
    assert (
        "Could you tell me a little more about what you need"
        not in instructions.split("# CONVERSATION RULES", 1)[0]
    )
    assert "no tools or authority" in instructions


def test_realtime_prompt_does_not_send_raw_or_unbounded_ticket_context() -> None:
    instructions = build_realtime_intake_instructions(
        IntakeDetails(
            description="private description that is not provider context",
            operational_question="Q" * 500,
            known_context="raw chat history must not be sent",
            missing_information=("area_or_region",),
        )
    )

    assert "private description" not in instructions
    assert "raw chat history" not in instructions
    assert "Q" * 100 not in instructions
    assert '"operational_question"' in instructions


def test_voice_configuration_restores_valid_state_and_rejects_disabled_use() -> None:
    store = MemoryStateStore()
    store.save(VOICE_MODEL_NAMESPACE, {"model": "voice-b", "enabled": True})
    settings = Settings(
        environment="test",
        openai_realtime_model="voice-a",
        available_openai_realtime_models=["voice-a", "voice-b"],
    )
    service = VoiceModelService(settings, AuditLog(), store)
    assert service.state().model == "voice-b"
    assert service.state().enabled is True
    with pytest.raises(AppError, match="OpenAI voice is not configured"):
        service.require_enabled()

    disabled_store = MemoryStateStore()
    disabled = VoiceModelService(settings, AuditLog(), disabled_store)
    with pytest.raises(AppError, match="Realtime voice is not enabled"):
        disabled.require_enabled()


def test_voice_configuration_migrates_an_unavailable_persisted_model() -> None:
    store = MemoryStateStore()
    store.save(
        VOICE_MODEL_NAMESPACE,
        {"model": "gpt-realtime-2.1-mini", "enabled": True},
    )

    service = VoiceModelService(Settings(environment="test"), AuditLog(), store)

    assert service.state().model == "gpt-realtime-2.1"
    assert store.load(VOICE_MODEL_NAMESPACE) == {
        "model": "gpt-realtime-2.1",
        "enabled": True,
    }


def test_voice_connection_test_distinguishes_saved_from_verified() -> None:
    captured: dict[str, str] = {}

    def succeed(**kwargs: str) -> None:
        captured.update(kwargs)

    service = VoiceModelService(
        Settings(environment="test"),
        AuditLog(),
        MemoryStateStore(),
        connection_tester=succeed,
    )
    missing = service.test_connection()
    assert missing.ok is False
    assert missing.message == "No dedicated Voice API key is saved."

    service.configure_api_key("admin", "admin@example.test", "sk-dedicated-voice-key")
    result = service.test_connection()
    assert result.ok is True
    assert result.message == "OpenAI Realtime accepted gpt-realtime-2.1."
    assert captured == {"api_key": "sk-dedicated-voice-key", "model": "gpt-realtime-2.1"}


def test_voice_connection_test_returns_a_sanitised_provider_failure() -> None:
    def fail(**_kwargs: str) -> None:
        raise AppError(503, "voice_provider_credentials_rejected", "The key was rejected.")

    service = VoiceModelService(
        Settings(environment="test"), AuditLog(), MemoryStateStore(), connection_tester=fail
    )
    service.configure_api_key("admin", "admin@example.test", "sk-dedicated-voice-key")
    result = service.test_connection()
    assert result.ok is False
    assert result.message == "The key was rejected."


def test_voice_key_configuration_rolls_back_when_audit_fails() -> None:
    store = MemoryStateStore()
    settings = Settings(environment="test")
    service = VoiceModelService(settings, FailingAuditLog(), store)

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.configure_api_key("admin", "admin@example.test", "sk-dedicated-voice-key")

    assert service.state().api_key_configured is False
    assert service.state().enabled is False
    assert store.load(VOICE_MODEL_NAMESPACE) == {
        "model": "gpt-realtime-2.1",
        "enabled": False,
    }
    assert store.load(integration_secret_namespace(VOICE_CREDENTIAL_NAME)) == {}


def test_voice_model_configuration_rolls_back_when_audit_fails() -> None:
    store = MemoryStateStore()
    settings = Settings(
        environment="test",
        openai_realtime_model="voice-a",
        available_openai_realtime_models=["voice-a", "voice-b"],
    )
    service = VoiceModelService(settings, AuditLog(), store)
    service.configure_api_key("admin", "admin@example.test", "sk-dedicated-voice-key")
    failing = VoiceModelService(settings, FailingAuditLog(), store)

    with pytest.raises(RuntimeError, match="audit unavailable"):
        failing.configure("admin", "admin@example.test", "voice-b", True)

    assert failing.state() == VoiceModelState("voice-a", ("voice-a", "voice-b"), False, True)
    restarted = VoiceModelService(settings, AuditLog(), store)
    assert restarted.state() == VoiceModelState("voice-a", ("voice-a", "voice-b"), False, True)


def test_voice_key_model_and_enabled_state_survive_restart_without_plaintext() -> None:
    store = MemoryStateStore()
    settings = Settings(
        environment="test",
        openai_realtime_model="voice-a",
        available_openai_realtime_models=["voice-a", "voice-b"],
    )
    service = VoiceModelService(settings, AuditLog(), store)
    service.configure_api_key("admin", "admin@example.test", "sk-dedicated-voice-key")
    service.configure("admin", "admin@example.test", "voice-b", True)

    envelope = store.load(integration_secret_namespace(VOICE_CREDENTIAL_NAME))
    assert envelope
    assert "sk-dedicated-voice-key" not in str(envelope)

    restarted = VoiceModelService(settings, AuditLog(), store)
    assert restarted.api_key() == "sk-dedicated-voice-key"
    assert restarted.state() == VoiceModelState("voice-b", ("voice-a", "voice-b"), True, True)


def test_voice_session_defends_against_an_inconsistent_missing_key_state() -> None:
    settings = Settings(environment="test")
    session_service = VoiceSessionService(
        settings,
        EnabledVoiceModels(),  # type: ignore[arg-type]
        UnusedAdmission(),  # type: ignore[arg-type]
        AuditLog(),
    )

    with pytest.raises(AppError, match="OpenAI voice is not configured"):
        session_service.create(uuid4(), "v=0\r\nm=audio offer\r\n")


def test_voice_session_releases_capacity_when_start_audit_fails() -> None:
    settings = Settings(environment="test")
    admission = VoiceSessionAdmission(max_concurrent=1, max_per_principal=1, ttl_seconds=60)
    service = VoiceSessionService(
        settings,
        EnabledVoiceModels("sk-voice-test-key"),  # type: ignore[arg-type]
        admission,
        FailingAuditLog(),
        call_creator=lambda **_kwargs: "v=0\r\n",
    )
    user_id = uuid4()

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.create(user_id, "v=0\r\nm=audio offer\r\n")

    assert isinstance(admission.acquire(user_id), UUID)


def test_voice_session_releases_capacity_when_provider_deadline_expires() -> None:
    def timed_out_call(**_kwargs: object) -> str:
        raise AppError(
            502,
            "voice_provider_unavailable",
            "The voice provider is temporarily unavailable.",
        )

    admission = VoiceSessionAdmission(max_concurrent=1, max_per_principal=1, ttl_seconds=60)
    service = VoiceSessionService(
        Settings(environment="test"),
        EnabledVoiceModels("sk-voice-test-key"),  # type: ignore[arg-type]
        admission,
        AuditLog(),
        call_creator=timed_out_call,
    )
    user_id = uuid4()

    with pytest.raises(AppError, match="temporarily unavailable"):
        service.create(user_id, "v=0\r\nm=audio offer\r\n")

    assert isinstance(admission.acquire(user_id), UUID)


def test_voice_session_ignores_an_unknown_release_token() -> None:
    audit_log = AuditLog()
    service = VoiceSessionService(
        Settings(environment="test"),
        EnabledVoiceModels("sk-voice-test-key"),  # type: ignore[arg-type]
        VoiceSessionAdmission(max_concurrent=1, max_per_principal=1, ttl_seconds=60),
        audit_log,
    )

    service.release(uuid4(), uuid4())

    assert audit_log.list_events() == ()


def test_voice_admission_bounds_principals_and_expires_leases() -> None:
    now = datetime(2026, 7, 15, tzinfo=UTC)
    clock = lambda: now  # noqa: E731
    admission = VoiceSessionAdmission(
        max_concurrent=2, max_per_principal=1, ttl_seconds=60, clock=clock
    )
    first_user = uuid4()
    token = admission.acquire(first_user)
    with pytest.raises(AppError, match="capacity"):
        admission.acquire(first_user)
    admission.acquire(uuid4())
    with pytest.raises(AppError, match="capacity"):
        admission.acquire(uuid4())
    assert admission.release(uuid4(), token) is False
    assert admission.release(first_user, uuid4()) is False

    now += timedelta(seconds=61)
    replacement = admission.acquire(first_user)
    assert isinstance(replacement, UUID)
    assert admission.release(first_user, replacement) is True
