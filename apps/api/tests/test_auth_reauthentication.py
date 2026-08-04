"""Focused evidence for password reauthentication of sensitive operations."""

import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.repositories.auth import LoginAttemptRepository, SeedUserRepository, SessionRepository
from coeus.services.audit import AuditLog
from coeus.services.auth import AuthService
from coeus.services.passwords import PasswordHasher

SEED_CREDENTIAL = "CoeusLocal1!"


def _service() -> AuthService:
    settings = Settings(environment="test", argon2_memory_cost=8_192)
    password_hasher = PasswordHasher(settings)
    return AuthService(
        settings,
        SeedUserRepository(settings, password_hasher),
        SessionRepository(),
        LoginAttemptRepository(),
        password_hasher,
        AuditLog(),
    )


def test_reauthentication_verifies_current_principal_and_records_evidence() -> None:
    service = _service()
    login = service.login("admin@example.test", SEED_CREDENTIAL)
    authenticated = service.require_session(login.session_token)

    service.reauthenticate(authenticated, SEED_CREDENTIAL, client_ip="203.0.113.30")

    assert service.audit_log.list_events()[-1].event_type == "reauthentication_success"


def test_reauthentication_rejects_wrong_credential_without_exposing_it() -> None:
    service = _service()
    login = service.login("admin@example.test", SEED_CREDENTIAL)
    authenticated = service.require_session(login.session_token)

    with pytest.raises(AppError) as exc_info:
        service.reauthenticate(authenticated, "not-the-password")

    assert exc_info.value.code == "authentication_failed"
    event = service.audit_log.list_events()[-1]
    assert event.event_type == "reauthentication_failure"
    assert "not-the-password" not in str(event.metadata)
