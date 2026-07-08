from datetime import UTC, datetime
from uuid import uuid4

import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.registration import RegistrationRequest, RegistrationStatus
from coeus.repositories.auth import SeedUserRepository
from coeus.repositories.registration import RegistrationRepository
from coeus.services.audit import AuditLog
from coeus.services.passwords import PasswordHasher
from coeus.services.registration import RegistrationService


def _service() -> tuple[RegistrationService, SeedUserRepository, RegistrationRepository]:
    settings = Settings(environment="test", argon2_memory_cost=8_192)
    password_hasher = PasswordHasher(settings)
    users = SeedUserRepository(settings, password_hasher)
    registrations = RegistrationRepository()
    service = RegistrationService(
        settings=settings,
        users=users,
        registrations=registrations,
        password_hasher=password_hasher,
        audit_log=AuditLog(max_events=100),
    )
    return service, users, registrations


def _pending(username: str) -> RegistrationRequest:
    return RegistrationRequest(
        registration_id=uuid4(),
        username=username,
        display_name="Pending Operator",
        justification="Mock duties.",
        password_hash="argon2-mock-hash",  # noqa: S106 - synthetic fixture hash, not a secret.
        status=RegistrationStatus.PENDING,
        created_at=datetime.now(UTC),
        decided_at=None,
        decided_by_user_id=None,
    )


def test_approval_rejects_registration_when_username_became_taken() -> None:
    service, users, registrations = _service()
    admin = users.get_by_username("admin@example.test")
    assert admin is not None
    registration = _pending("admin@example.test")
    registrations.save(registration)

    with pytest.raises(AppError) as raised:
        service.approve(admin, registration.registration_id)

    assert raised.value.status_code == 409
    assert raised.value.code == "username_taken"
    decided = registrations.get(registration.registration_id)
    assert decided is not None
    assert decided.status == RegistrationStatus.REJECTED
    assert decided.decided_by_user_id == admin.user_id


def test_approval_rolls_back_account_when_decision_save_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, users, registrations = _service()
    admin = users.get_by_username("admin@example.test")
    assert admin is not None
    registration = _pending("new.operator@example.test")
    registrations.save(registration)
    original_save = registrations.save

    def fail_approved_save(candidate: RegistrationRequest) -> None:
        if candidate.status == RegistrationStatus.APPROVED:
            raise RuntimeError("simulated registration decision failure")
        original_save(candidate)

    monkeypatch.setattr(registrations, "save", fail_approved_save)

    with pytest.raises(RuntimeError, match="simulated registration decision failure"):
        service.approve(admin, registration.registration_id)

    assert users.get_by_username("new.operator@example.test") is None
    current = registrations.get(registration.registration_id)
    assert current is not None
    assert current.status == RegistrationStatus.PENDING
