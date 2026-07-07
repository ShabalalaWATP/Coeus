from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from coeus.core.config import Settings
from coeus.domain.auth import RoleName, SessionRecord, UserAccount
from coeus.domain.rbac import permissions_for_roles
from coeus.persistence.codec import decode_value, encode_value
from coeus.persistence.state_store import StateStore
from coeus.services.passwords import PasswordHasher


class AttemptStoreFull(RuntimeError):
    pass


class SeedUserRepository:
    def __init__(
        self,
        settings: Settings,
        password_hasher: PasswordHasher,
        state_store: StateStore | None = None,
    ) -> None:
        self._state_store = state_store
        self._initialising = True
        self._users_by_username: dict[str, UserAccount] = {}
        self._users_by_id: dict[UUID, UserAccount] = {}
        self._seed_users(settings.local_seed_credential, password_hasher)
        self._initialising = False
        self._restore_or_persist()

    def _seed_users(self, seed_credential: str, password_hasher: PasswordHasher) -> None:
        for username, display_name, roles, is_active in _seed_user_specs():
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
        self._users_by_username[user.username.casefold()] = user
        self._users_by_id[user.user_id] = user
        self._persist()

    def get_by_username(self, username: str) -> UserAccount | None:
        return self._users_by_username.get(username.casefold())

    def get_by_id(self, user_id: UUID) -> UserAccount | None:
        return self._users_by_id.get(user_id)

    def list_users(self) -> tuple[UserAccount, ...]:
        return tuple(self._users_by_id.values())

    def _restore_or_persist(self) -> None:
        if self._state_store is None:
            return
        payload = self._state_store.load("users")
        if payload is None:
            self._persist()
            return
        seeded_users = dict(self._users_by_username)
        users = tuple(decode_value(item) for item in payload.get("users", []))
        self._users_by_username = {user.username.casefold(): user for user in users}
        self._users_by_id = {user.user_id: user for user in users}
        for username, user in seeded_users.items():
            if username not in self._users_by_username:
                self.save(user)

    def _persist(self) -> None:
        if self._state_store is None or self._initialising:
            return
        users = sorted(self._users_by_id.values(), key=lambda user: user.username)
        self._state_store.save("users", {"users": [encode_value(user) for user in users]})


class SessionRepository:
    def __init__(self, state_store: StateStore | None = None) -> None:
        self._state_store = state_store
        self._sessions: dict[str, SessionRecord] = {}
        self._restore_or_persist()

    def save(self, session: SessionRecord) -> None:
        self._sessions[session.session_id] = session
        self._persist()

    def get(self, session_id: str) -> SessionRecord | None:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._persist()

    def delete_for_user(self, user_id: UUID) -> None:
        for session_id, session in list(self._sessions.items()):
            if session.user_id == user_id:
                self.delete(session_id)

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
    def __init__(self, max_entries: int = 10_000) -> None:
        if max_entries < 1:
            raise ValueError("Login attempt max_entries must be at least 1.")
        self._max_entries = max_entries
        self._attempts: dict[str, tuple[tuple[datetime, ...], datetime | None]] = {}

    def get_lockout_until(self, username: str) -> datetime | None:
        attempts = self._attempts.get(username.casefold())
        if attempts is None:
            return None
        return attempts[1]

    def record_failure(
        self, username: str, threshold: int, lockout_seconds: int
    ) -> datetime | None:
        key = username.casefold()
        now = datetime.now(UTC)
        if (
            key not in self._attempts
            and len(self._attempts) >= self._max_entries
            and not self._evict_non_locked_attempt(now)
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
        return locked_until

    def reset(self, username: str) -> None:
        self._attempts.pop(username.casefold(), None)

    @property
    def entry_count(self) -> int:
        return len(self._attempts)

    def _evict_non_locked_attempt(self, now: datetime) -> bool:
        for key, (_moments, locked_until) in list(self._attempts.items()):
            if locked_until is None or locked_until <= now:
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

    def __init__(self, max_entries: int = 10_000) -> None:
        if max_entries < 1:
            raise ValueError("IP attempt max_entries must be at least 1.")
        self._max_entries = max_entries
        self._attempts: dict[str, list[datetime]] = {}

    def within_budget(self, source: str, max_attempts: int, window_seconds: int) -> bool:
        now = datetime.now(UTC)
        window_start = now - timedelta(seconds=window_seconds)
        recent = [moment for moment in self._attempts.get(source, []) if moment > window_start]
        if (
            source not in self._attempts
            and len(self._attempts) >= self._max_entries
            and not self._evict_stale(window_start)
        ):
            return False
        recent.append(now)
        self._attempts[source] = recent
        return len(recent) <= max_attempts

    @property
    def entry_count(self) -> int:
        return len(self._attempts)

    def _evict_stale(self, window_start: datetime) -> bool:
        for source, moments in list(self._attempts.items()):
            if not moments or moments[-1] <= window_start:
                self._attempts.pop(source)
                return True
        return False


def _seed_user_specs() -> Iterable[tuple[str, str, frozenset[RoleName], bool]]:
    return (
        (
            "admin@example.test",
            "Admin Operator",
            frozenset({RoleName.ADMINISTRATOR}),
            True,
        ),
        ("user@example.test", "Customer User", frozenset({RoleName.USER}), True),
        (
            "colleague@example.test",
            "Customer Colleague",
            frozenset({RoleName.USER}),
            True,
        ),
        (
            "rfa.manager@example.test",
            "RFA Manager",
            frozenset({RoleName.RFA_MANAGER}),
            True,
        ),
        (
            "rfa.team@example.test",
            "RFA Team Member",
            frozenset({RoleName.RFA_TEAM_MEMBER}),
            True,
        ),
        (
            "collection.manager@example.test",
            "Collection Manager",
            frozenset({RoleName.COLLECTION_MANAGER}),
            True,
        ),
        (
            "collection.team@example.test",
            "Collection Team Member",
            frozenset({RoleName.COLLECTION_TEAM_MEMBER}),
            True,
        ),
        (
            "store.manager@example.test",
            "Intelligence Store Manager",
            frozenset({RoleName.INTELLIGENCE_STORE_MANAGER}),
            True,
        ),
        (
            "analyst@example.test",
            "Intelligence Analyst",
            frozenset({RoleName.INTELLIGENCE_ANALYST}),
            True,
        ),
        (
            "analyst.maritime@example.test",
            "Maritime Assessment Analyst",
            frozenset({RoleName.INTELLIGENCE_ANALYST}),
            True,
        ),
        (
            "analyst.cyber@example.test",
            "Cyber Threat Analyst",
            frozenset({RoleName.INTELLIGENCE_ANALYST}),
            True,
        ),
        (
            "analyst.geo@example.test",
            "Geospatial Assessment Analyst",
            frozenset({RoleName.INTELLIGENCE_ANALYST}),
            True,
        ),
        (
            "qc.manager@example.test",
            "QC Manager",
            frozenset({RoleName.QUALITY_CONTROL_MANAGER}),
            True,
        ),
        ("disabled@example.test", "Disabled User", frozenset({RoleName.USER}), False),
    )
