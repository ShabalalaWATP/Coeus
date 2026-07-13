from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from threading import RLock
from uuid import UUID, uuid4

from coeus.application.ports.passwords import PasswordHashPort
from coeus.core.config import Settings
from coeus.domain.auth import SessionRecord, UserAccount
from coeus.domain.rbac import permissions_for_roles
from coeus.persistence.codec import decode_value, encode_value
from coeus.persistence.state_store import StateStore
from coeus.repositories.auth_seed import seed_user_specs


class AttemptStoreFull(RuntimeError):
    """Raised when the bounded username attempt store cannot evict entries."""


LoginAttemptState = tuple[tuple[datetime, ...], datetime | None]


@dataclass(frozen=True)
class LoginAttemptReset:
    previous: LoginAttemptState | None
    version: int


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
        for username, display_name, roles, is_active in seed_user_specs():
            account = UserAccount(
                user_id=uuid4(),
                username=username,
                display_name=display_name,
                roles=roles,
                permissions=permissions_for_roles(roles),
                password_hash=password_hasher.hash(seed_credential),
                is_active=is_active,
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
        users = tuple(
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

    def delete(self, session_id: str) -> None:
        with self._lock:
            sessions = dict(self._sessions)
            self._sessions.pop(session_id, None)
            try:
                self._persist()
            except Exception:
                self._sessions = sessions
                raise

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


class LoginAttemptRepository:
    def __init__(
        self,
        max_entries: int = 10_000,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if max_entries < 1:
            raise ValueError("Login attempt max_entries must be at least 1.")
        self._max_entries = max_entries
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = RLock()
        self._attempts: dict[str, LoginAttemptState] = {}
        self._versions: dict[str, int] = {}

    def get_lockout_until(self, username: str) -> datetime | None:
        with self._lock:
            attempts = self._attempts.get(username.casefold())
            if attempts is None:
                return None
            return attempts[1]

    def active_lockout_until(self, username: str) -> datetime | None:
        """Return an active lock, atomically removing only an expired state."""
        with self._lock:
            key = username.casefold()
            attempts = self._attempts.get(key)
            if attempts is None:
                return None
            locked_until = attempts[1]
            if locked_until is not None and locked_until > self._clock():
                return locked_until
            if locked_until is not None:
                self._attempts.pop(key)
                self._versions[key] = self._versions.get(key, 0) + 1
            return None

    def record_failure(
        self, username: str, threshold: int, lockout_seconds: int
    ) -> datetime | None:
        with self._lock:
            key = username.casefold()
            now = self._clock()
            if (
                key not in self._attempts
                and len(self._attempts) >= self._max_entries
                and not self._evict_stale_attempt(now, lockout_seconds)
            ):
                raise AttemptStoreFull("Login attempt store is full.")
            moments, _locked_until = self._attempts.get(key, ((), None))
            # Failures older than the lockout window no longer count, so a slow
            # trickle of failures cannot keep an account locked out indefinitely.
            window_start = now - timedelta(seconds=lockout_seconds)
            recent = tuple(moment for moment in moments if moment > window_start)
            recent = (*recent, now)
            locked_until = (
                now + timedelta(seconds=lockout_seconds) if len(recent) >= threshold else None
            )
            self._attempts[key] = (recent, locked_until)
            self._versions[key] = self._versions.get(key, 0) + 1
            return locked_until

    def reset(self, username: str) -> LoginAttemptReset:
        with self._lock:
            key = username.casefold()
            previous = self._attempts.pop(key, None)
            version = self._versions.get(key, 0) + 1
            self._versions[key] = version
            return LoginAttemptReset(previous=previous, version=version)

    def restore_reset(self, username: str, reset: LoginAttemptReset) -> None:
        """Restore one reset only when no concurrent mutation followed it."""
        with self._lock:
            key = username.casefold()
            if self._versions.get(key, 0) != reset.version or key in self._attempts:
                return
            if reset.previous is not None:
                self._attempts[key] = reset.previous
                self._versions[key] = reset.version + 1

    def snapshot(self) -> dict[str, LoginAttemptState]:
        with self._lock:
            return dict(self._attempts)

    def restore(self, attempts: dict[str, LoginAttemptState]) -> None:
        with self._lock:
            self._attempts = dict(attempts)
            for key in set(self._versions) | set(attempts):
                self._versions[key] = self._versions.get(key, 0) + 1

    @property
    def entry_count(self) -> int:
        with self._lock:
            return len(self._attempts)

    def _evict_stale_attempt(self, now: datetime, lockout_seconds: int) -> bool:
        window_start = now - timedelta(seconds=lockout_seconds)
        for key, (moments, locked_until) in list(self._attempts.items()):
            has_recent_failure = any(moment > window_start for moment in moments)
            has_active_lock = locked_until is not None and locked_until > now
            if not has_recent_failure and not has_active_lock:
                self._attempts.pop(key)
                return True
        return False


class IpAttemptRepository:
    """Bounded per-source sliding window for authentication attempts.

    Complements the username-scoped lockout: a single source cannot spray many
    usernames without tripping this budget. Storage is bounded; when full and
    nothing stale can be evicted, new sources are over budget rather than
    bypassing throttling.
    """

    def __init__(
        self,
        max_entries: int = 10_000,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if max_entries < 1:
            raise ValueError("IP attempt max_entries must be at least 1.")
        self._max_entries = max_entries
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = RLock()
        self._attempts: dict[str, list[datetime]] = {}

    def within_budget(self, source: str, max_attempts: int, window_seconds: int) -> bool:
        with self._lock:
            now = self._clock()
            window_start = now - timedelta(seconds=window_seconds)
            recent = [moment for moment in self._attempts.get(source, []) if moment > window_start]
            if source not in self._attempts:
                self._prune_stale(window_start)
                if len(self._attempts) >= self._max_entries:
                    return False
            if len(recent) >= max_attempts:
                self._attempts[source] = recent[:max_attempts]
                return False
            recent.append(now)
            self._attempts[source] = recent
            return True

    @property
    def entry_count(self) -> int:
        with self._lock:
            return len(self._attempts)

    def _prune_stale(self, window_start: datetime) -> None:
        for source, moments in list(self._attempts.items()):
            if not moments or moments[-1] <= window_start:
                self._attempts.pop(source)
