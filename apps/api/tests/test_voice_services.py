from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.persistence.state_store import MemoryStateStore
from coeus.services.audit import AuditLog
from coeus.services.voice_admission import VoiceSessionAdmission
from coeus.services.voice_models import VOICE_MODEL_NAMESPACE, VoiceModelService, VoiceModelState
from coeus.services.voice_sessions import VoiceSessionService


class FailingAuditLog(AuditLog):
    def record(self, *_args: object, **_kwargs: object):  # type: ignore[no-untyped-def]
        raise RuntimeError("audit unavailable")


class EnabledVoiceModels:
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def require_enabled(self) -> VoiceModelState:
        return VoiceModelState("gpt-realtime-2.1-mini", ("gpt-realtime-2.1-mini",), True, True)

    def api_key(self) -> str | None:
        return self._api_key


class UnusedAdmission:
    def acquire(self, *_args: object):  # type: ignore[no-untyped-def]
        raise AssertionError("admission should not be reached")


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


def test_voice_key_configuration_rolls_back_when_audit_fails() -> None:
    store = MemoryStateStore()
    settings = Settings(environment="test")
    service = VoiceModelService(settings, FailingAuditLog(), store)

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.configure_api_key("admin", "admin@example.test", "sk-dedicated-voice-key")

    assert service.state().api_key_configured is False
    assert service.state().enabled is False
    assert store.load(VOICE_MODEL_NAMESPACE) == {
        "model": "gpt-realtime-2.1-mini",
        "enabled": False,
    }


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


def test_voice_session_releases_capacity_when_start_audit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "coeus.services.voice_sessions.create_realtime_call", lambda **_kwargs: "v=0\r\n"
    )
    settings = Settings(environment="test")
    admission = VoiceSessionAdmission(max_concurrent=1, max_per_principal=1, ttl_seconds=60)
    service = VoiceSessionService(
        settings,
        EnabledVoiceModels("sk-voice-test-key"),  # type: ignore[arg-type]
        admission,
        FailingAuditLog(),
    )
    user_id = uuid4()

    with pytest.raises(RuntimeError, match="audit unavailable"):
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
