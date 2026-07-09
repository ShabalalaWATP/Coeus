import pytest

from coeus.core.config import Settings
from coeus.repositories.auth import LoginAttemptRepository, SeedUserRepository, SessionRepository
from coeus.services.audit import AuditLog
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
