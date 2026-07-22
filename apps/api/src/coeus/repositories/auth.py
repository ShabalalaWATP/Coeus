from collections.abc import Callable
from dataclasses import replace
from threading import RLock
from uuid import UUID, uuid4

from coeus.application.ports.passwords import PasswordHashPort
from coeus.core.config import Settings
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
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
from coeus.repositories.sessions import (
    SessionRepository as SessionRepository,
)
from coeus.repositories.sessions import (
    SessionStoreFull as SessionStoreFull,
)

Confirmation = Callable[[], object]

__all__ = [
    "AttemptStoreFull",
    "IpAttemptRepository",
    "LoginAttemptRepository",
    "LoginAttemptReset",
    "LoginAttemptState",
    "SeedUserRepository",
    "SessionRepository",
    "SessionStoreFull",
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

    def save_if_current_with_confirmation(
        self,
        expected: UserAccount,
        updated: UserAccount,
        confirm: Confirmation,
    ) -> bool:
        """Replace one exact account snapshot and confirm its dependent effects.

        The user lock remains held while ``confirm`` runs, so another account
        security mutation cannot interleave between the current-state check and
        required session or audit work.
        """
        if (
            expected.user_id != updated.user_id
            or expected.username.casefold() != updated.username.casefold()
        ):
            raise ValueError("Conditional user updates cannot change account identity.")
        with self._lock:
            if self._users_by_id.get(expected.user_id) != expected:
                return False
            self._replace_with_confirmation(updated, confirm)
            return True

    def save_if_current_authorised_with_confirmation(
        self,
        expected_actor: UserAccount,
        required_permission: Permission,
        expected_target: UserAccount,
        updated_target: UserAccount,
        confirm: Confirmation,
    ) -> bool:
        """Replace a target only while the captured actor remains authoritative."""
        if (
            expected_target.user_id != updated_target.user_id
            or expected_target.username.casefold() != updated_target.username.casefold()
        ):
            raise ValueError("Conditional user updates cannot change account identity.")
        with self._lock:
            current_actor = self._users_by_id.get(expected_actor.user_id)
            if (
                current_actor != expected_actor
                or not current_actor.is_active
                or required_permission not in current_actor.permissions
                or self._users_by_id.get(expected_target.user_id) != expected_target
            ):
                return False
            self._replace_with_confirmation(updated_target, confirm)
            return True

    def confirm_current_authority(
        self,
        expected_actor: UserAccount,
        required_permissions: frozenset[Permission],
        confirm: Confirmation,
    ) -> bool:
        """Run a dependent commit only while an exact actor snapshot remains authoritative."""
        with self._lock:
            current_actor = self._users_by_id.get(expected_actor.user_id)
            if (
                current_actor != expected_actor
                or not current_actor.is_active
                or not required_permissions.issubset(current_actor.permissions)
            ):
                return False
            confirm()
            return True

    def _replace_with_confirmation(self, updated: UserAccount, confirm: Confirmation) -> None:
        usernames = dict(self._users_by_username)
        users = dict(self._users_by_id)
        self._users_by_username[updated.username.casefold()] = updated
        self._users_by_id[updated.user_id] = updated
        try:
            self._persist()
            confirm()
        except Exception:
            self._users_by_username = usernames
            self._users_by_id = users
            self._persist()
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
