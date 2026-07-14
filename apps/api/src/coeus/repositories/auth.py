from dataclasses import replace
from threading import RLock
from uuid import UUID, uuid4

from coeus.application.ports.passwords import PasswordHashPort
from coeus.core.config import Settings
from coeus.domain.auth import SessionRecord, UserAccount
from coeus.domain.rbac import permissions_for_roles
from coeus.persistence.codec import decode_value, encode_value
from coeus.persistence.state_store import StateStore
from coeus.repositories.auth_attempts import (
    AttemptStoreFull,
    IpAttemptRepository,
    LoginAttemptRepository,
    LoginAttemptReset,
    LoginAttemptState,
)
from coeus.repositories.auth_seed import reconcile_seed_user_identities, seed_user_specs

__all__ = [
    "AttemptStoreFull",
    "IpAttemptRepository",
    "LoginAttemptRepository",
    "LoginAttemptReset",
    "LoginAttemptState",
    "SeedUserRepository",
    "SessionRepository",
]


class SeedUserRepository:
    def __init__(
        self,
        settings: Settings,
        password_hasher: PasswordHashPort,
        state_store: StateStore | None = None,
    ) -> None:
        self._state_store = state_store
        self._lock = RLock()
        self._initialising = True
        self._users_by_username: dict[str, UserAccount] = {}
        self._users_by_id: dict[UUID, UserAccount] = {}
        self._seed_users(settings.local_seed_credential, password_hasher)
        self._initialising = False
        self._restore_or_persist()

    def _seed_users(self, seed_credential: str, password_hasher: PasswordHashPort) -> None:
        for spec in seed_user_specs():
            account = UserAccount(
                user_id=uuid4(),
                username=spec.username,
                display_name=spec.display_name,
                roles=spec.roles,
                permissions=permissions_for_roles(spec.roles),
                password_hash=password_hasher.hash(seed_credential),
                is_active=spec.is_active,
                clearance_level=3,
            )
            self.save(account)

    def save(self, user: UserAccount) -> None:
        with self._lock:
            usernames = dict(self._users_by_username)
            users = dict(self._users_by_id)
            self._users_by_username[user.username.casefold()] = user
            self._users_by_id[user.user_id] = user
            try:
                self._persist()
            except Exception:
                self._users_by_username = usernames
                self._users_by_id = users
                raise

    def delete(self, user_id: UUID) -> None:
        with self._lock:
            usernames = dict(self._users_by_username)
            users = dict(self._users_by_id)
            user = self._users_by_id.pop(user_id, None)
            if user is not None:
                self._users_by_username.pop(user.username.casefold(), None)
                try:
                    self._persist()
                except Exception:
                    self._users_by_username = usernames
                    self._users_by_id = users
                    raise

    def get_by_username(self, username: str) -> UserAccount | None:
        with self._lock:
            return self._users_by_username.get(username.casefold())

    def get_by_id(self, user_id: UUID) -> UserAccount | None:
        with self._lock:
            return self._users_by_id.get(user_id)

    def list_users(self) -> tuple[UserAccount, ...]:
        with self._lock:
            return tuple(self._users_by_id.values())

    def _restore_or_persist(self) -> None:
        if self._state_store is None:
            return
        payload = self._state_store.load("users")
        if payload is None:
            self._persist()
            return
        seeded_users = dict(self._users_by_username)
        # Roles are the persisted source of truth; permissions are re-derived
        # from the current role definitions so code-level permission changes
        # (grants AND revocations) apply to existing accounts on startup.
        users = reconcile_seed_user_identities(
            _with_current_permissions(decode_value(item)) for item in payload.get("users", [])
        )
        self._users_by_username = {user.username.casefold(): user for user in users}
        self._users_by_id = {user.user_id: user for user in users}
        self._persist()
        for username, user in seeded_users.items():
            if username not in self._users_by_username:
                self.save(user)

    def _persist(self) -> None:
        if self._state_store is None or self._initialising:
            return
        users = sorted(self._users_by_id.values(), key=lambda user: user.username)
        self._state_store.save("users", {"users": [encode_value(user) for user in users]})


def _with_current_permissions(user: UserAccount) -> UserAccount:
    return replace(user, permissions=permissions_for_roles(user.roles))


class SessionRepository:
    def __init__(self, state_store: StateStore | None = None) -> None:
        self._state_store = state_store
        self._lock = RLock()
        self._sessions: dict[str, SessionRecord] = {}
        self._restore_or_persist()

    def save(self, session: SessionRecord) -> None:
        with self._lock:
            sessions = dict(self._sessions)
            self._sessions[session.session_id] = session
            try:
                self._persist()
            except Exception:
                self._sessions = sessions
                raise

    def get(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            sessions = dict(self._sessions)
            deleted = self._sessions.pop(session_id, None)
            if deleted is None:
                return None
            try:
                self._persist()
            except Exception:
                self._sessions = sessions
                raise
            return deleted

    def replace_if_current(self, expected_id: str, replacement: SessionRecord) -> bool:
        """Atomically replace one active session without reviving a stale token."""
        with self._lock:
            current = self._sessions.get(expected_id)
            if current is None or current.user_id != replacement.user_id:
                return False
            if replacement.session_id != expected_id and replacement.session_id in self._sessions:
                return False
            sessions = dict(self._sessions)
            self._sessions.pop(expected_id)
            self._sessions[replacement.session_id] = replacement
            try:
                self._persist()
            except Exception:
                self._sessions = sessions
                raise
            return True

    def delete_for_user(self, user_id: UUID) -> tuple[SessionRecord, ...]:
        with self._lock:
            sessions = dict(self._sessions)
            deleted = tuple(
                session for session in self._sessions.values() if session.user_id == user_id
            )
            if not deleted:
                return ()
            for session in deleted:
                self._sessions.pop(session.session_id, None)
            try:
                self._persist()
            except Exception:
                self._sessions = sessions
                raise
            return deleted

    def _restore_or_persist(self) -> None:
        if self._state_store is None:
            return
        payload = self._state_store.load("sessions")
        if payload is None:
            self._persist()
            return
        sessions = tuple(decode_value(item) for item in payload.get("sessions", []))
        self._sessions = {session.session_id: session for session in sessions}

    def _persist(self) -> None:
        if self._state_store is None:
            return
        sessions = sorted(self._sessions.values(), key=lambda session: session.created_at)
        self._state_store.save(
            "sessions",
            {"sessions": [encode_value(session) for session in sessions]},
        )
