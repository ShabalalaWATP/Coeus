from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from coeus.core.config import Settings
from coeus.domain.auth import RoleName, SessionRecord, UserAccount
from coeus.domain.rbac import permissions_for_roles
from coeus.services.passwords import PasswordHasher


class SeedUserRepository:
    def __init__(self, settings: Settings, password_hasher: PasswordHasher) -> None:
        self._users_by_username: dict[str, UserAccount] = {}
        self._users_by_id: dict[UUID, UserAccount] = {}
        self._seed_users(settings.local_seed_credential, password_hasher)

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

    def get_by_username(self, username: str) -> UserAccount | None:
        return self._users_by_username.get(username.casefold())

    def get_by_id(self, user_id: UUID) -> UserAccount | None:
        return self._users_by_id.get(user_id)

    def list_users(self) -> tuple[UserAccount, ...]:
        return tuple(self._users_by_id.values())


class SessionRepository:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}

    def save(self, session: SessionRecord) -> None:
        self._sessions[session.session_id] = session

    def get(self, session_id: str) -> SessionRecord | None:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def delete_for_user(self, user_id: UUID) -> None:
        for session_id, session in list(self._sessions.items()):
            if session.user_id == user_id:
                self.delete(session_id)


class LoginAttemptRepository:
    def __init__(self, max_entries: int = 10_000) -> None:
        if max_entries < 1:
            raise ValueError("Login attempt max_entries must be at least 1.")
        self._max_entries = max_entries
        self._attempts: dict[str, tuple[int, datetime | None]] = {}

    def get_lockout_until(self, username: str) -> datetime | None:
        attempts = self._attempts.get(username.casefold())
        if attempts is None:
            return None
        return attempts[1]

    def record_failure(
        self, username: str, threshold: int, lockout_seconds: int
    ) -> datetime | None:
        key = username.casefold()
        if key not in self._attempts and len(self._attempts) >= self._max_entries:
            self._attempts.pop(next(iter(self._attempts)))
        count, _locked_until = self._attempts.get(key, (0, None))
        count += 1
        locked_until = (
            datetime.now(UTC) + timedelta(seconds=lockout_seconds) if count >= threshold else None
        )
        self._attempts[key] = (count, locked_until)
        return locked_until

    def reset(self, username: str) -> None:
        self._attempts.pop(username.casefold(), None)

    @property
    def entry_count(self) -> int:
        return len(self._attempts)


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
            "analyst@example.test",
            "Intelligence Analyst",
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
