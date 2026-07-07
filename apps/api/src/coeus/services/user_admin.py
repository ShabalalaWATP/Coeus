from dataclasses import replace
from secrets import token_urlsafe
from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.rbac import permissions_for_roles
from coeus.repositories.auth import LoginAttemptRepository, SeedUserRepository, SessionRepository
from coeus.services.audit import AuditLog
from coeus.services.passwords import PasswordHasher

MIN_CLEARANCE = 1
MAX_CLEARANCE = 5


class UserAdminService:
    """Administrator management of accounts: roles, clearance and status.

    Every change invalidates the target user's sessions so stale privileges
    cannot outlive the decision, and administrators cannot act on their own
    account, which prevents accidental self-lockout and self-elevation.
    """

    def __init__(
        self,
        users: SeedUserRepository,
        sessions: SessionRepository,
        login_attempts: LoginAttemptRepository,
        password_hasher: PasswordHasher,
        audit_log: AuditLog,
    ) -> None:
        self._users = users
        self._sessions = sessions
        self._login_attempts = login_attempts
        self._password_hasher = password_hasher
        self._audit_log = audit_log

    def list_users(self, actor: UserAccount) -> tuple[UserAccount, ...]:
        self._require(actor, Permission.USER_ASSIGN_ROLE)
        return tuple(sorted(self._users.list_users(), key=lambda user: user.username))

    def set_roles(
        self, actor: UserAccount, user_id: UUID, roles: frozenset[RoleName]
    ) -> UserAccount:
        self._require(actor, Permission.USER_ASSIGN_ROLE)
        if not roles:
            raise AppError(422, "roles_required", "At least one role is required.")
        user = self._target(actor, user_id)
        updated = replace(user, roles=roles, permissions=permissions_for_roles(roles))
        self._apply(updated)
        self._audit_log.record(
            "user_roles_changed",
            str(actor.user_id),
            {"user_id": str(user_id), "roles": ",".join(sorted(role.value for role in roles))},
        )
        return updated

    def set_clearance(self, actor: UserAccount, user_id: UUID, clearance: int) -> UserAccount:
        self._require(actor, Permission.USER_ASSIGN_ROLE)
        if clearance < MIN_CLEARANCE or clearance > MAX_CLEARANCE:
            raise AppError(422, "clearance_invalid", "Clearance must be between 1 and 5.")
        user = self._target(actor, user_id)
        updated = replace(user, clearance_level=clearance)
        self._apply(updated)
        self._audit_log.record(
            "user_clearance_changed",
            str(actor.user_id),
            {"user_id": str(user_id), "clearance_level": str(clearance)},
        )
        return updated

    def set_active(self, actor: UserAccount, user_id: UUID, is_active: bool) -> UserAccount:
        self._require(actor, Permission.USER_DISABLE)
        user = self._target(actor, user_id)
        updated = replace(user, is_active=is_active)
        self._apply(updated)
        self._audit_log.record(
            "user_enabled" if is_active else "user_disabled",
            str(actor.user_id),
            {"user_id": str(user_id)},
        )
        return updated

    def reset_credential(self, actor: UserAccount, user_id: UUID) -> str:
        self._require(actor, Permission.USER_DISABLE)
        user = self._target(actor, user_id)
        temporary_credential = f"Istari-{token_urlsafe(18)}"
        updated = replace(
            user,
            password_hash=self._password_hasher.hash(temporary_credential),
            # A temporary credential must be rotated by the user at next login.
            password_reset_required=True,
        )
        self._apply(updated)
        self._login_attempts.reset(user.username)
        self._audit_log.record(
            "user_credential_reset",
            str(actor.user_id),
            {"user_id": str(user_id)},
        )
        return temporary_credential

    def _target(self, actor: UserAccount, user_id: UUID) -> UserAccount:
        if user_id == actor.user_id:
            raise AppError(
                409,
                "self_modification",
                "Administrators cannot modify their own account.",
            )
        user = self._users.get_by_id(user_id)
        if user is None:
            raise AppError(404, "user_not_found", "User was not found.")
        return user

    def _apply(self, user: UserAccount) -> None:
        self._users.save(user)
        # Privilege or status changes must not outlive existing sessions.
        self._sessions.delete_for_user(user.user_id)

    @staticmethod
    def _require(actor: UserAccount, permission: Permission) -> None:
        if permission not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
