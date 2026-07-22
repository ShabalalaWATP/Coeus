from dataclasses import replace
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from threading import Barrier, Event, Thread
from uuid import UUID

import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.auth import RoleName, SessionRecord, UserAccount
from coeus.domain.rbac import permissions_for_roles
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


def _session_for(user_id: UUID) -> SessionRecord:
    now = datetime.now(UTC)
    return SessionRecord(
        session_id="target-session",
        user_id=user_id,
        csrf_token=token_urlsafe(12),
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )


def _mutate_user(
    service: UserAdminService,
    actor: UserAccount,
    target: UserAccount,
    mutation: str,
) -> UserAccount:
    if mutation == "roles":
        return service.set_roles(actor, target.user_id, frozenset({RoleName.INTELLIGENCE_ANALYST}))
    if mutation == "clearance":
        return service.set_clearance(actor, target.user_id, 4)
    return service.set_active(actor, target.user_id, False)


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


def test_role_change_rolls_back_user_when_user_persistence_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, users, _sessions, audit_log = _service()
    admin = users.get_by_username("admin@example.test")
    target = users.get_by_username("user@example.test")
    assert admin is not None
    assert target is not None

    def fail_persist() -> None:
        raise RuntimeError("simulated user persistence failure")

    monkeypatch.setattr(users, "_persist", fail_persist)

    with pytest.raises(RuntimeError, match="simulated user persistence failure"):
        service.set_roles(admin, target.user_id, frozenset({RoleName.INTELLIGENCE_ANALYST}))

    assert users.get_by_id(target.user_id) == target
    assert audit_log.list_events() == ()


def test_role_change_rolls_back_user_and_sessions_when_audit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, users, sessions, audit_log = _service()
    admin = users.get_by_username("admin@example.test")
    target = users.get_by_username("user@example.test")
    assert admin is not None
    assert target is not None
    session = _session_for(target.user_id)
    sessions.save(session)

    def fail_record(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated audit failure")

    monkeypatch.setattr(audit_log, "record", fail_record)

    with pytest.raises(RuntimeError, match="simulated audit failure"):
        service.set_roles(admin, target.user_id, frozenset({RoleName.INTELLIGENCE_ANALYST}))

    assert users.get_by_id(target.user_id) == target
    assert sessions.get(session.session_id) == session


def test_credential_reset_rolls_back_target_state_when_audit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, users, sessions, audit_log = _service()
    admin = users.get_by_username("admin@example.test")
    target = users.get_by_username("user@example.test")
    assert admin is not None and target is not None
    session = _session_for(target.user_id)
    sessions.save(session)
    service._login_attempts.record_failure(target.username, 3, 60)
    attempts_before = service._login_attempts.snapshot()

    def fail_record(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated audit failure")

    monkeypatch.setattr(audit_log, "record", fail_record)

    with pytest.raises(RuntimeError, match="simulated audit failure"):
        service.reset_credential(admin, target.user_id)

    assert users.get_by_id(target.user_id) == target
    assert sessions.get(session.session_id) == session
    assert service._login_attempts.snapshot() == attempts_before


def test_user_admin_rejects_invalid_targets_values_and_permissions() -> None:
    service, users, _sessions, _audit = _service()
    admin = users.get_by_username("admin@example.test")
    target = users.get_by_username("user@example.test")
    assert admin is not None
    assert target is not None

    with pytest.raises(AppError, match="At least one role"):
        service.set_roles(admin, target.user_id, frozenset())
    with pytest.raises(AppError, match="Clearance must be between"):
        service.set_clearance(admin, target.user_id, 0)
    with pytest.raises(AppError, match="User was not found"):
        service.set_active(admin, UUID(int=0), True)
    with pytest.raises(AppError, match="Permission denied"):
        service.set_active(target, admin.user_id, False)


@pytest.mark.parametrize("mutation", ["roles", "clearance", "status"])
def test_current_administrator_authority_commits_user_changes(mutation: str) -> None:
    service, users, sessions, audit_log = _service()
    actor = users.get_by_username("admin@example.test")
    target = users.get_by_username("user@example.test")
    assert actor is not None and target is not None
    target_session = _session_for(target.user_id)
    sessions.save(target_session)

    updated = _mutate_user(service, actor, target, mutation)

    assert users.get_by_id(target.user_id) == updated
    assert sessions.get(target_session.session_id) is None
    event_type = {
        "roles": "user_roles_changed",
        "clearance": "user_clearance_changed",
        "status": "user_disabled",
    }[mutation]
    assert any(
        event.event_type == event_type and event.metadata.get("user_id") == str(target.user_id)
        for event in audit_log.list_events()
    )


@pytest.mark.parametrize("mutation", ["roles", "clearance", "status"])
def test_user_change_cannot_commit_after_actor_authority_revocation(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    service, users, sessions, audit_log = _service()
    actor = users.get_by_username("admin@example.test")
    target = users.get_by_username("user@example.test")
    revoker = users.get_by_username("jioc.team@example.test")
    assert actor is not None and target is not None and revoker is not None
    administrator_roles = frozenset({RoleName.ADMINISTRATOR})
    revoker = replace(
        revoker,
        roles=administrator_roles,
        permissions=permissions_for_roles(administrator_roles),
    )
    users.save(revoker)
    target_session = _session_for(target.user_id)
    sessions.save(target_session)
    mutation_started = Event()
    resume_mutation = Event()
    original_target = service._target

    def gated_target(captured_actor: UserAccount, user_id: UUID) -> UserAccount:
        resolved = original_target(captured_actor, user_id)
        if captured_actor.user_id == actor.user_id and user_id == target.user_id:
            mutation_started.set()
            assert resume_mutation.wait(timeout=5)
        return resolved

    monkeypatch.setattr(service, "_target", gated_target)
    outcome: dict[str, object] = {}

    def mutate_target() -> None:
        try:
            outcome["updated"] = _mutate_user(service, actor, target, mutation)
        except BaseException as error:
            outcome["error"] = error

    worker = Thread(target=mutate_target)
    worker.start()
    assert mutation_started.wait(timeout=5)
    try:
        service.set_roles(revoker, actor.user_id, frozenset({RoleName.USER}))
    finally:
        resume_mutation.set()
    worker.join(timeout=5)

    assert not worker.is_alive()
    assert isinstance(outcome.get("error"), AppError)
    assert outcome["error"].code == "user_stale"
    assert users.get_by_id(target.user_id) == target
    assert sessions.get(target_session.session_id) == target_session
    assert not any(
        event.metadata.get("user_id") == str(target.user_id) for event in audit_log.list_events()
    )


@pytest.mark.parametrize("revocation", ["roles", "status"])
def test_credential_reset_cannot_commit_after_actor_authority_revocation(
    revocation: str,
) -> None:
    service, users, sessions, audit_log = _service()
    actor = users.get_by_username("admin@example.test")
    target = users.get_by_username("user@example.test")
    revoker = users.get_by_username("jioc.team@example.test")
    assert actor is not None and target is not None and revoker is not None
    revoker = replace(
        revoker,
        roles=frozenset({RoleName.ADMINISTRATOR}),
        permissions=permissions_for_roles(frozenset({RoleName.ADMINISTRATOR})),
    )
    users.save(revoker)
    target_session = _session_for(target.user_id)
    sessions.save(target_session)
    service._login_attempts.record_failure(target.username, 3, 60)
    attempts_before = service._login_attempts.snapshot()

    hash_started = Event()
    resume_hash = Event()
    original_hash = service._password_hasher.hash

    def blocking_hash(credential: str) -> str:
        hash_started.set()
        assert resume_hash.wait(timeout=5)
        return original_hash(credential)

    service._password_hasher.hash = blocking_hash
    outcome: dict[str, object] = {}

    def reset_target() -> None:
        try:
            outcome["credential"] = service.reset_credential(actor, target.user_id)
        except BaseException as error:
            outcome["error"] = error

    worker = Thread(target=reset_target)
    worker.start()
    assert hash_started.wait(timeout=5)
    if revocation == "roles":
        service.set_roles(revoker, actor.user_id, frozenset({RoleName.USER}))
    else:
        service.set_active(revoker, actor.user_id, False)
    resume_hash.set()
    worker.join(timeout=5)

    assert not worker.is_alive()
    assert "credential" not in outcome
    assert isinstance(outcome.get("error"), AppError)
    assert outcome["error"].code == "user_stale"
    assert users.get_by_id(target.user_id) == target
    assert sessions.get(target_session.session_id) == target_session
    assert service._login_attempts.snapshot() == attempts_before
    assert not any(event.event_type == "user_credential_reset" for event in audit_log.list_events())


def test_only_one_concurrent_credential_reset_can_commit() -> None:
    service, users, _sessions, audit_log = _service()
    actor = users.get_by_username("admin@example.test")
    target = users.get_by_username("user@example.test")
    assert actor is not None and target is not None
    both_hashing = Barrier(2)
    original_hash = service._password_hasher.hash

    def coordinated_hash(credential: str) -> str:
        both_hashing.wait(timeout=5)
        return original_hash(credential)

    service._password_hasher.hash = coordinated_hash
    outcomes: list[tuple[str, object]] = []

    def reset_target() -> None:
        try:
            outcomes.append(("success", service.reset_credential(actor, target.user_id)))
        except AppError as error:
            outcomes.append(("error", error))

    workers = [Thread(target=reset_target) for _index in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=5)

    assert all(not worker.is_alive() for worker in workers)
    successes = [value for outcome, value in outcomes if outcome == "success"]
    errors = [value for outcome, value in outcomes if outcome == "error"]
    assert len(successes) == 1
    assert len(errors) == 1
    assert isinstance(successes[0], str)
    assert isinstance(errors[0], AppError)
    assert errors[0].code == "user_stale"
    current = users.get_by_id(target.user_id)
    assert current is not None
    assert service._password_hasher.verify(current.password_hash, successes[0])
    assert current.credential_version == target.credential_version + 1
    assert (
        sum(event.event_type == "user_credential_reset" for event in audit_log.list_events()) == 1
    )
