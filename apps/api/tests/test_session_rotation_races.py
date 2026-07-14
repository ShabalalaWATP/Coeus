from dataclasses import replace
from threading import Barrier, Event, Thread, current_thread

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
    hasher = PasswordHasher(settings)
    return AuthService(
        settings=settings,
        users=SeedUserRepository(settings, hasher),
        sessions=SessionRepository(),
        login_attempts=LoginAttemptRepository(),
        password_hasher=hasher,
        audit_log=AuditLog(),
    )


def test_rotation_cannot_create_a_descendant_after_logout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    original = service.login("user@example.test", SEED_CREDENTIAL)
    rotation_checked = Event()
    allow_rotation = Event()
    original_require_session = service.require_session
    outcome: dict[str, object] = {}

    def gated_require_session(session_id: str | None):  # type: ignore[no-untyped-def]
        authenticated = original_require_session(session_id)
        if current_thread().name == "rotate":
            rotation_checked.set()
            assert allow_rotation.wait(timeout=5)
        return authenticated

    monkeypatch.setattr(service, "require_session", gated_require_session)

    def rotate() -> None:
        try:
            outcome["rotation"] = service.rotate_session(original.session_token)
        except AppError as exc:
            outcome["error"] = exc

    thread = Thread(target=rotate, name="rotate")
    thread.start()
    assert rotation_checked.wait(timeout=5)
    service.logout(original.session_token)
    allow_rotation.set()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert isinstance(outcome.get("error"), AppError)
    assert outcome["error"].code == "not_authenticated"  # type: ignore[union-attr]
    with pytest.raises(AppError):
        original_require_session(original.session_token)
    assert service._sessions._sessions == {}


def test_logout_cannot_report_success_after_rotation_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    original = service.login("user@example.test", SEED_CREDENTIAL)
    logout_checked = Event()
    allow_logout = Event()
    original_require_session = service.require_session
    outcome: dict[str, object] = {}

    def gated_require_session(session_id: str | None):  # type: ignore[no-untyped-def]
        authenticated = original_require_session(session_id)
        if current_thread().name == "logout":
            logout_checked.set()
            assert allow_logout.wait(timeout=5)
        return authenticated

    monkeypatch.setattr(service, "require_session", gated_require_session)

    def logout() -> None:
        try:
            service.logout(original.session_token)
            outcome["completed"] = True
        except AppError as exc:
            outcome["error"] = exc

    thread = Thread(target=logout, name="logout")
    thread.start()
    assert logout_checked.wait(timeout=5)
    rotated_token, _rotated = service.rotate_session(original.session_token)
    allow_logout.set()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert isinstance(outcome.get("error"), AppError)
    assert outcome["error"].code == "not_authenticated"  # type: ignore[union-attr]
    assert original_require_session(rotated_token).user.username == "user@example.test"
    assert "logout" not in [event.event_type for event in service.audit_log.list_events()]


def test_rotation_cannot_survive_password_change_revocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    original = service.login("user@example.test", SEED_CREDENTIAL)
    rotation_checked = Event()
    allow_rotation = Event()
    original_require_session = service.require_session
    outcome: dict[str, object] = {}

    def gated_require_session(session_id: str | None):  # type: ignore[no-untyped-def]
        authenticated = original_require_session(session_id)
        if current_thread().name == "rotate":
            rotation_checked.set()
            assert allow_rotation.wait(timeout=5)
        return authenticated

    monkeypatch.setattr(service, "require_session", gated_require_session)

    def rotate() -> None:
        try:
            outcome["rotation"] = service.rotate_session(original.session_token)
        except AppError as exc:
            outcome["error"] = exc

    thread = Thread(target=rotate, name="rotate")
    thread.start()
    assert rotation_checked.wait(timeout=5)
    changed = service.change_password(
        original.session_token,
        SEED_CREDENTIAL,
        "ReplacementPass1!",
    )
    allow_rotation.set()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert isinstance(outcome.get("error"), AppError)
    assert outcome["error"].code == "not_authenticated"  # type: ignore[union-attr]
    assert original_require_session(changed.session_token).user.username == "user@example.test"
    with pytest.raises(AppError):
        original_require_session(original.session_token)


def test_only_one_concurrent_rotation_can_replace_the_source_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    original = service.login("user@example.test", SEED_CREDENTIAL)
    both_checked = Barrier(2)
    original_require_session = service.require_session
    outcomes: list[tuple[str, object]] = []

    def gated_require_session(session_id: str | None):  # type: ignore[no-untyped-def]
        authenticated = original_require_session(session_id)
        if current_thread().name.startswith("rotate"):
            both_checked.wait(timeout=5)
        return authenticated

    monkeypatch.setattr(service, "require_session", gated_require_session)

    def rotate() -> None:
        try:
            outcomes.append(("success", service.rotate_session(original.session_token)))
        except AppError as exc:
            outcomes.append(("error", exc))

    threads = [Thread(target=rotate, name=f"rotate-{index}") for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    successes = [value for outcome, value in outcomes if outcome == "success"]
    errors = [value for outcome, value in outcomes if outcome == "error"]
    assert len(successes) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], AppError)
    assert errors[0].code == "not_authenticated"
    rotated_token, _session = successes[0]  # type: ignore[misc]
    assert original_require_session(rotated_token).user.username == "user@example.test"
    with pytest.raises(AppError):
        original_require_session(original.session_token)


def test_atomic_rotation_rolls_back_when_session_persistence_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    original = service.login("user@example.test", SEED_CREDENTIAL)
    authenticated = service.require_session(original.session_token)
    replacement_token, replacement = service._prepare_session(authenticated.user)

    def fail_persist() -> None:
        raise RuntimeError("synthetic persistence failure")

    monkeypatch.setattr(service._sessions, "_persist", fail_persist)

    with pytest.raises(RuntimeError, match="synthetic persistence failure"):
        service._sessions.replace_if_current(authenticated.session.session_id, replacement)

    assert service.require_session(original.session_token).user.username == "user@example.test"
    with pytest.raises(AppError):
        service.require_session(replacement_token)


def test_session_is_rejected_when_credential_version_changes() -> None:
    service = _service()
    original = service.login("user@example.test", SEED_CREDENTIAL)
    user = service._users.get_by_id(original.user.user_id)
    assert user is not None
    service._users.save(replace(user, credential_version=user.credential_version + 1))

    with pytest.raises(AppError) as error:
        service.require_session(original.session_token)

    assert error.value.code == "not_authenticated"
    with pytest.raises(AppError):
        service.require_session(original.session_token)


def test_old_password_login_cannot_issue_after_password_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    original = service.login("user@example.test", SEED_CREDENTIAL)
    login_ready = Event()
    allow_login = Event()
    original_create_session = service._create_session
    outcome: dict[str, object] = {}

    def gated_create_session(user):  # type: ignore[no-untyped-def]
        if current_thread().name == "old-password-login":
            login_ready.set()
            assert allow_login.wait(timeout=5)
        return original_create_session(user)

    monkeypatch.setattr(service, "_create_session", gated_create_session)

    def stale_login() -> None:
        try:
            outcome["login"] = service.login("user@example.test", SEED_CREDENTIAL)
        except AppError as exc:
            outcome["error"] = exc

    thread = Thread(target=stale_login, name="old-password-login")
    thread.start()
    assert login_ready.wait(timeout=5)
    changed = service.change_password(
        original.session_token,
        SEED_CREDENTIAL,
        "ReplacementPass1!",
    )
    allow_login.set()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert isinstance(outcome.get("error"), AppError)
    assert outcome["error"].code == "authentication_failed"  # type: ignore[union-attr]
    assert service.require_session(changed.session_token).user.username == "user@example.test"
    assert len(service._sessions._sessions) == 1


def test_password_change_revokes_a_rotation_that_wins_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    original = service.login("user@example.test", SEED_CREDENTIAL)
    password_checked = Event()
    allow_password_change = Event()
    original_verify = service._password_hasher.verify
    outcome: dict[str, object] = {}

    def gated_verify(password_hash: str, credential: str) -> bool:
        verified = original_verify(password_hash, credential)
        if current_thread().name == "password-change":
            password_checked.set()
            assert allow_password_change.wait(timeout=5)
        return verified

    monkeypatch.setattr(service._password_hasher, "verify", gated_verify)

    def change_password() -> None:
        outcome["changed"] = service.change_password(
            original.session_token,
            SEED_CREDENTIAL,
            "ReplacementPass1!",
        )

    thread = Thread(target=change_password, name="password-change")
    thread.start()
    assert password_checked.wait(timeout=5)
    rotated_token, _session = service.rotate_session(original.session_token)
    allow_password_change.set()
    thread.join(timeout=5)

    assert not thread.is_alive()
    changed = outcome["changed"]
    assert service.require_session(changed.session_token).user.username == "user@example.test"  # type: ignore[union-attr]
    with pytest.raises(AppError):
        service.require_session(rotated_token)
    assert len(service._sessions._sessions) == 1


def test_atomic_rotation_rejects_missing_cross_user_and_colliding_replacements() -> None:
    service = _service()
    source = service.login("user@example.test", SEED_CREDENTIAL)
    other = service.login("admin@example.test", SEED_CREDENTIAL)
    sessions = service._sessions
    original_state = dict(sessions._sessions)

    assert not sessions.replace_if_current("missing", source.session)
    assert not sessions.replace_if_current(source.session.session_id, other.session)
    colliding = replace(other.session, user_id=source.user.user_id)
    assert not sessions.replace_if_current(source.session.session_id, colliding)
    assert sessions._sessions == original_state
