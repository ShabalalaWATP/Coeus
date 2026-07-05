import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.repositories.auth import LoginAttemptRepository, SeedUserRepository, SessionRepository
from coeus.services.audit import AuditLog
from coeus.services.auth import AuthService
from coeus.services.passwords import PasswordHasher

SEED_CREDENTIAL = "CoeusLocal1!"


class RecordingPasswordHasher:
    def __init__(self) -> None:
        self.verified_hashes: list[str] = []

    def hash(self, credential: str) -> str:
        return f"hash:{credential}"

    def verify(self, stored_hash: str, credential: str) -> bool:
        self.verified_hashes.append(stored_hash)
        return False

    def needs_rehash(self, stored_hash: str) -> bool:
        return False


def build_auth_service(settings: Settings | None = None) -> AuthService:
    resolved_settings = settings or Settings(environment="test", argon2_memory_cost=8_192)
    password_hasher = PasswordHasher(resolved_settings)
    return AuthService(
        settings=resolved_settings,
        users=SeedUserRepository(resolved_settings, password_hasher),
        sessions=SessionRepository(),
        login_attempts=LoginAttemptRepository(),
        password_hasher=password_hasher,
        audit_log=AuditLog(),
    )


def build_auth_service_with_repositories(
    settings: Settings,
) -> tuple[AuthService, LoginAttemptRepository, AuditLog]:
    password_hasher = PasswordHasher(settings)
    attempts = LoginAttemptRepository(max_entries=settings.login_attempt_max_entries)
    audit_log = AuditLog(max_events=settings.audit_log_max_events)
    service = AuthService(
        settings=settings,
        users=SeedUserRepository(settings, password_hasher),
        sessions=SessionRepository(),
        login_attempts=attempts,
        password_hasher=password_hasher,
        audit_log=audit_log,
    )
    return service, attempts, audit_log


def test_unknown_user_login_still_runs_password_verifier() -> None:
    settings = Settings(environment="test", argon2_memory_cost=8_192)
    password_hasher = RecordingPasswordHasher()
    service = AuthService(
        settings=settings,
        users=SeedUserRepository(settings, password_hasher),
        sessions=SessionRepository(),
        login_attempts=LoginAttemptRepository(),
        password_hasher=password_hasher,
        audit_log=AuditLog(),
    )

    with pytest.raises(AppError) as exc_info:
        service.login("missing@example.test", "wrong")

    assert exc_info.value.code == "authentication_failed"
    assert len(password_hasher.verified_hashes) == 1


def test_login_failure_state_is_bounded() -> None:
    settings = Settings(
        environment="test",
        argon2_memory_cost=8_192,
        audit_log_max_events=4,
        login_attempt_max_entries=3,
    )
    service, attempts, audit_log = build_auth_service_with_repositories(settings)

    for index in range(8):
        with pytest.raises(AppError):
            service.login(f"missing-{index}@example.test", "wrong")

    assert attempts.entry_count == 3
    assert len(audit_log.list_events()) == 4


def test_username_spraying_does_not_evict_active_lockout() -> None:
    settings = Settings(
        environment="test",
        argon2_memory_cost=8_192,
        login_lockout_threshold=2,
        login_attempt_max_entries=3,
    )
    service, attempts, _audit_log = build_auth_service_with_repositories(settings)

    for _index in range(settings.login_lockout_threshold):
        with pytest.raises(AppError):
            service.login("admin@example.test", "wrong")
    for index in range(8):
        with pytest.raises(AppError):
            service.login(f"missing-{index}@example.test", "wrong")

    with pytest.raises(AppError) as exc_info:
        service.login("admin@example.test", SEED_CREDENTIAL)

    assert exc_info.value.code == "account_locked"
    assert attempts.entry_count == settings.login_attempt_max_entries


def test_expired_session_is_rejected_and_removed() -> None:
    service = build_auth_service(
        Settings(environment="test", session_ttl_seconds=-1, argon2_memory_cost=8_192)
    )
    result = service.login("admin@example.test", SEED_CREDENTIAL)

    with pytest.raises(AppError) as exc_info:
        service.require_session(result.session.session_id)

    assert exc_info.value.code == "session_expired"


def test_missing_session_is_not_authenticated() -> None:
    service = build_auth_service()

    with pytest.raises(AppError) as exc_info:
        service.require_session(None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "not_authenticated"


def test_replace_session_id_revokes_existing_session() -> None:
    service = build_auth_service()
    first = service.login("admin@example.test", SEED_CREDENTIAL)
    second = service.login(
        "admin@example.test",
        SEED_CREDENTIAL,
        replace_session_id=first.session.session_id,
    )

    with pytest.raises(AppError):
        service.require_session(first.session.session_id)
    assert service.require_session(second.session.session_id).user.username == "admin@example.test"
