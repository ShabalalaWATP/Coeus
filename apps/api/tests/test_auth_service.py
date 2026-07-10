from datetime import UTC, datetime, timedelta

import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.repositories.auth import (
    IpAttemptRepository,
    LoginAttemptRepository,
    SeedUserRepository,
    SessionRepository,
)
from coeus.services.audit import AuditLog
from coeus.services.auth import AuthService, hash_session_id
from coeus.services.passwords import PasswordHasher

SEED_CREDENTIAL = "CoeusLocal1!"


class RecordingPasswordHasher(PasswordHasher):
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


def test_source_throttling_limits_username_spray() -> None:
    settings = Settings(
        environment="test",
        argon2_memory_cost=8_192,
        auth_ip_max_attempts=2,
    )
    service, _attempts, audit_log = build_auth_service_with_repositories(settings)

    for index in range(settings.auth_ip_max_attempts):
        with pytest.raises(AppError) as exc_info:
            service.login(f"missing-{index}@example.test", "wrong", client_ip="203.0.113.10")
        assert exc_info.value.code == "authentication_failed"
    with pytest.raises(AppError) as throttled:
        service.login("another@example.test", "wrong", client_ip="203.0.113.10")

    assert throttled.value.status_code == 429
    assert throttled.value.code == "too_many_attempts"
    assert audit_log.list_events()[-1].event_type == "auth_throttled"


def test_source_attempt_repository_is_bounded_and_fails_closed_when_full() -> None:
    attempts = IpAttemptRepository(max_entries=1)

    assert attempts.within_budget("203.0.113.1", max_attempts=1, window_seconds=300)
    assert not attempts.within_budget("203.0.113.2", max_attempts=1, window_seconds=300)
    assert attempts.entry_count == 1


def test_login_attempt_store_saturation_fails_closed() -> None:
    settings = Settings(
        environment="test",
        argon2_memory_cost=8_192,
        login_lockout_threshold=1,
        login_attempt_max_entries=1,
    )
    service, attempts, audit_log = build_auth_service_with_repositories(settings)

    with pytest.raises(AppError):
        service.login("admin@example.test", "wrong")
    with pytest.raises(AppError) as exc_info:
        service.login("missing@example.test", "wrong")

    assert attempts.entry_count == 1
    assert exc_info.value.status_code == 429
    assert exc_info.value.code == "too_many_attempts"
    assert audit_log.list_events()[-1].event_type == "auth_throttled"


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
        service.require_session(result.session_token)

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
        replace_session_id=first.session_token,
    )

    with pytest.raises(AppError):
        service.require_session(first.session_token)
    assert service.require_session(second.session_token).user.username == "admin@example.test"


def test_sessions_are_stored_hashed_at_rest() -> None:
    service = build_auth_service()
    result = service.login("admin@example.test", SEED_CREDENTIAL)

    assert result.session.session_id != result.session_token
    assert result.session.session_id == hash_session_id(result.session_token)
    assert service.require_session(result.session_token).user.username == "admin@example.test"
    # The stored hash must not be usable as a cookie value.
    with pytest.raises(AppError) as exc_info:
        service.require_session(result.session.session_id)
    assert exc_info.value.code == "not_authenticated"


def test_stale_login_failures_decay_outside_lockout_window() -> None:
    attempts = LoginAttemptRepository()
    stale = datetime.now(UTC) - timedelta(seconds=600)
    attempts._attempts["user@example.test"] = ((stale, stale), None)

    locked_until = attempts.record_failure("user@example.test", threshold=3, lockout_seconds=300)

    assert locked_until is None
    assert attempts.get_lockout_until("user@example.test") is None


def test_login_failures_within_window_still_trigger_lockout() -> None:
    attempts = LoginAttemptRepository()

    first = attempts.record_failure("user@example.test", threshold=2, lockout_seconds=300)
    second = attempts.record_failure("user@example.test", threshold=2, lockout_seconds=300)

    assert first is None
    assert second is not None
    assert second > datetime.now(UTC)
