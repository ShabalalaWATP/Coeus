import pytest

from coeus.core.config import Settings
from coeus.repositories.auth import LoginAttemptRepository, SeedUserRepository, SessionRepository
from coeus.services.audit import AuditEvent, AuditLog
from coeus.services.auth import AuthService
from coeus.services.passwords import PasswordHasher

SEED_CREDENTIAL = "CoeusLocal1!"


def _service() -> AuthService:
    settings = Settings(environment="test", argon2_memory_cost=8_192)
    password_hasher = PasswordHasher(settings)
    return AuthService(
        settings=settings,
        users=SeedUserRepository(settings, password_hasher),
        sessions=SessionRepository(),
        login_attempts=LoginAttemptRepository(),
        password_hasher=password_hasher,
        audit_log=AuditLog(),
    )


def test_password_change_rolls_back_user_when_session_revocation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    result = service.login("user@example.test", SEED_CREDENTIAL)
    original = service._users.get_by_username("user@example.test")
    assert original is not None

    def fail_delete_for_user(_user_id: object) -> None:
        raise RuntimeError("simulated session revocation failure")

    monkeypatch.setattr(service._sessions, "delete_for_user", fail_delete_for_user)

    with pytest.raises(RuntimeError, match="simulated session revocation failure"):
        service.change_password(result.session_token, SEED_CREDENTIAL, "ReplacementPass1!")

    current = service._users.get_by_username("user@example.test")
    assert current is not None
    assert current == original
    assert service.require_session(result.session_token).user == original
    assert service._password_hasher.verify(current.password_hash, SEED_CREDENTIAL)
    assert not service._password_hasher.verify(current.password_hash, "ReplacementPass1!")
    assert "password_changed" not in [event.event_type for event in service.audit_log.list_events()]


def test_login_rolls_back_session_and_attempts_when_audit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    first = service.login("user@example.test", SEED_CREDENTIAL)
    service._login_attempts.record_failure("user@example.test", threshold=3, lockout_seconds=300)
    original_record = service.audit_log.record

    def fail_login_success(
        event_type: str,
        actor_user_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> AuditEvent:
        if event_type == "login_success":
            raise RuntimeError("simulated audit failure")
        return original_record(event_type, actor_user_id, metadata)

    monkeypatch.setattr(service.audit_log, "record", fail_login_success)

    with pytest.raises(RuntimeError, match="simulated audit failure"):
        service.login(
            "user@example.test",
            SEED_CREDENTIAL,
            replace_session_id=first.session_token,
        )

    assert service.require_session(first.session_token).session == first.session
    assert service._sessions._sessions == {first.session.session_id: first.session}
    assert service._login_attempts.entry_count == 1


def test_password_change_rolls_back_user_sessions_and_attempts_when_audit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    result = service.login("user@example.test", SEED_CREDENTIAL)
    original = service._users.get_by_username("user@example.test")
    assert original is not None
    service._login_attempts.record_failure("user@example.test", threshold=3, lockout_seconds=300)
    original_record = service.audit_log.record

    def fail_password_changed(
        event_type: str,
        actor_user_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> AuditEvent:
        if event_type == "password_changed":
            raise RuntimeError("simulated audit failure")
        return original_record(event_type, actor_user_id, metadata)

    monkeypatch.setattr(service.audit_log, "record", fail_password_changed)

    with pytest.raises(RuntimeError, match="simulated audit failure"):
        service.change_password(result.session_token, SEED_CREDENTIAL, "ReplacementPass1!")

    current = service._users.get_by_username("user@example.test")
    assert current == original
    assert service.require_session(result.session_token).session == result.session
    assert service._sessions._sessions == {result.session.session_id: result.session}
    assert service._login_attempts.entry_count == 1
    assert service._password_hasher.verify(current.password_hash, SEED_CREDENTIAL)
    assert not service._password_hasher.verify(current.password_hash, "ReplacementPass1!")
    assert "password_changed" not in [event.event_type for event in service.audit_log.list_events()]


def test_logout_keeps_session_when_audit_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service()
    result = service.login("user@example.test", SEED_CREDENTIAL)

    original_record = service.audit_log.record

    def fail_logout(
        event_type: str,
        actor_user_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> AuditEvent:
        if event_type == "logout":
            raise RuntimeError("simulated audit failure")
        return original_record(event_type, actor_user_id, metadata)

    monkeypatch.setattr(service.audit_log, "record", fail_logout)

    with pytest.raises(RuntimeError, match="simulated audit failure"):
        service.logout(result.session_token)

    assert service.require_session(result.session_token).session == result.session


def test_logout_keeps_session_when_session_persistence_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    result = service.login("user@example.test", SEED_CREDENTIAL)

    def fail_persist() -> None:
        raise RuntimeError("simulated session persistence failure")

    monkeypatch.setattr(service._sessions, "_persist", fail_persist)

    with pytest.raises(RuntimeError, match="simulated session persistence failure"):
        service.logout(result.session_token)

    assert service.require_session(result.session_token).session == result.session


def test_login_restores_attempts_when_session_creation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    service._login_attempts.record_failure("user@example.test", threshold=3, lockout_seconds=300)

    def fail_session_save(_session: object) -> None:
        raise RuntimeError("simulated session save failure")

    monkeypatch.setattr(service._sessions, "save", fail_session_save)

    with pytest.raises(RuntimeError, match="simulated session save failure"):
        service.login("user@example.test", SEED_CREDENTIAL)

    assert service._login_attempts.entry_count == 1


def test_login_rollback_does_not_erase_a_following_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    service._login_attempts.record_failure("user@example.test", threshold=3, lockout_seconds=300)
    original_record = service.audit_log.record

    def fail_after_following_attempt(
        event_type: str,
        actor_user_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> AuditEvent:
        if event_type == "login_success":
            service._login_attempts.record_failure(
                "user@example.test", threshold=1, lockout_seconds=300
            )
            raise RuntimeError("simulated audit failure")
        return original_record(event_type, actor_user_id, metadata)

    monkeypatch.setattr(service.audit_log, "record", fail_after_following_attempt)

    with pytest.raises(RuntimeError, match="simulated audit failure"):
        service.login("user@example.test", SEED_CREDENTIAL)

    assert service._login_attempts.get_lockout_until("user@example.test") is not None
