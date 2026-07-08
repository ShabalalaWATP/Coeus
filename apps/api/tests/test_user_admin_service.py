import pytest

from coeus.core.config import Settings
from coeus.domain.auth import RoleName
from coeus.repositories.auth import LoginAttemptRepository, SeedUserRepository, SessionRepository
from coeus.services.audit import AuditLog
from coeus.services.passwords import PasswordHasher
from coeus.services.user_admin import UserAdminService


def _service() -> tuple[UserAdminService, SeedUserRepository, SessionRepository, AuditLog]:
    settings = Settings(environment="test", argon2_memory_cost=8_192)
    password_hasher = PasswordHasher(settings)
    users = SeedUserRepository(settings, password_hasher)
    sessions = SessionRepository()
    audit_log = AuditLog()
    service = UserAdminService(
        users=users,
        sessions=sessions,
        login_attempts=LoginAttemptRepository(),
        password_hasher=password_hasher,
        audit_log=audit_log,
    )
    return service, users, sessions, audit_log


def test_role_change_rolls_back_user_when_session_revocation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, users, sessions, audit_log = _service()
    admin = users.get_by_username("admin@example.test")
    target = users.get_by_username("user@example.test")
    assert admin is not None
    assert target is not None

    def fail_delete_for_user(_user_id: object) -> None:
        raise RuntimeError("simulated session revocation failure")

    monkeypatch.setattr(sessions, "delete_for_user", fail_delete_for_user)

    with pytest.raises(RuntimeError, match="simulated session revocation failure"):
        service.set_roles(admin, target.user_id, frozenset({RoleName.INTELLIGENCE_ANALYST}))

    current = users.get_by_id(target.user_id)
    assert current == target
    assert audit_log.list_events() == ()
