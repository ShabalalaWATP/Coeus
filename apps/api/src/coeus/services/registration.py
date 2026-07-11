from dataclasses import replace
from datetime import UTC, datetime
from threading import RLock
from uuid import UUID, uuid4

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.rbac import permissions_for_roles
from coeus.domain.registration import RegistrationRequest, RegistrationStatus
from coeus.repositories.auth import SeedUserRepository
from coeus.repositories.registration import (
    RegistrationCapacityFull,
    RegistrationRepository,
)
from coeus.services.audit import AuditLog
from coeus.services.passwords import PasswordHasher

REGISTERED_ROLE = RoleName.USER
REGISTERED_CLEARANCE_LEVEL = 1


class RegistrationService:
    """Self-service access requests reviewed and approved by administrators."""

    def __init__(
        self,
        settings: Settings,
        users: SeedUserRepository,
        registrations: RegistrationRepository,
        password_hasher: PasswordHasher,
        audit_log: AuditLog,
    ) -> None:
        self._settings = settings
        self._users = users
        self._registrations = registrations
        self._password_hasher = password_hasher
        self._audit_log = audit_log
        self._decision_lock = RLock()

    def submit(self, username: str, display_name: str, justification: str, password: str) -> None:
        """Record an access request. Responses stay generic to avoid account enumeration."""
        normalised = username.strip()
        if self._users.get_by_username(normalised) is not None:
            self._audit_log.record("registration_existing_user", None)
            return
        try:
            reservation = self._registrations.reserve_pending_slot(
                normalised, self._settings.registration_max_pending
            )
        except RegistrationCapacityFull as exc:
            self._audit_log.record("registration_throttled", None)
            raise AppError(
                429, "registration_throttled", "Too many pending requests. Try later."
            ) from exc
        if reservation is None:
            self._audit_log.record("registration_duplicate", None)
            return
        try:
            registration = RegistrationRequest(
                registration_id=uuid4(),
                username=normalised,
                display_name=display_name.strip(),
                justification=justification.strip(),
                password_hash=self._password_hasher.hash(password),
                status=RegistrationStatus.PENDING,
                created_at=datetime.now(UTC),
                decided_at=None,
                decided_by_user_id=None,
            )
            self._registrations.commit_reserved(reservation, registration)
        except Exception:
            self._registrations.release_reservation(reservation)
            raise
        try:
            self._audit_log.record(
                "registration_submitted",
                None,
                {"registration_id": str(registration.registration_id)},
            )
        except Exception:
            self._registrations.delete(registration.registration_id)
            raise

    def list_pending(self, actor: UserAccount) -> tuple[RegistrationRequest, ...]:
        self._require_reviewer(actor)
        return self._registrations.list_pending()

    def approve(self, actor: UserAccount, registration_id: UUID) -> RegistrationRequest:
        self._require_reviewer(actor)
        with self._decision_lock:
            registration = self._pending_registration(registration_id)
            if self._users.get_by_username(registration.username) is not None:
                decided = self._decide(registration, RegistrationStatus.REJECTED, actor)
                self._save_decision_and_audit(
                    registration,
                    decided,
                    "registration_rejected",
                    str(actor.user_id),
                    {"registration_id": str(registration_id), "reason": "username_taken"},
                )
                raise AppError(409, "username_taken", "An account already uses this username.")
            account = UserAccount(
                user_id=uuid4(),
                username=registration.username,
                display_name=registration.display_name,
                roles=frozenset({REGISTERED_ROLE}),
                permissions=permissions_for_roles(frozenset({REGISTERED_ROLE})),
                password_hash=registration.password_hash,
                is_active=True,
                clearance_level=REGISTERED_CLEARANCE_LEVEL,
            )
            self._users.save(account)
            decided = self._decide(registration, RegistrationStatus.APPROVED, actor)
            try:
                self._save_decision_and_audit(
                    registration,
                    decided,
                    "registration_approved",
                    str(actor.user_id),
                    {"registration_id": str(registration_id), "user_id": str(account.user_id)},
                )
            except Exception:
                self._users.delete(account.user_id)
                raise
            return decided

    def reject(self, actor: UserAccount, registration_id: UUID, reason: str) -> RegistrationRequest:
        self._require_reviewer(actor)
        with self._decision_lock:
            registration = self._pending_registration(registration_id)
            decided = self._decide(registration, RegistrationStatus.REJECTED, actor)
            self._save_decision_and_audit(
                registration,
                decided,
                "registration_rejected",
                str(actor.user_id),
                {"registration_id": str(registration_id), "reason": reason},
            )
            return decided

    def _pending_registration(self, registration_id: UUID) -> RegistrationRequest:
        registration = self._registrations.get(registration_id)
        if registration is None:
            raise AppError(404, "registration_not_found", "Registration was not found.")
        if registration.status != RegistrationStatus.PENDING:
            raise AppError(409, "registration_decided", "Registration is already decided.")
        return registration

    @staticmethod
    def _decide(
        registration: RegistrationRequest,
        status: RegistrationStatus,
        actor: UserAccount,
    ) -> RegistrationRequest:
        return replace(
            registration,
            status=status,
            decided_at=datetime.now(UTC),
            decided_by_user_id=actor.user_id,
        )

    def _save_decision_and_audit(
        self,
        original: RegistrationRequest,
        decided: RegistrationRequest,
        event_type: str,
        actor_user_id: str,
        metadata: dict[str, str],
    ) -> None:
        self._registrations.save(decided)
        try:
            self._audit_log.record(event_type, actor_user_id, metadata)
        except Exception:
            self._registrations.save(original)
            raise

    @staticmethod
    def _require_reviewer(actor: UserAccount) -> None:
        if Permission.USER_CREATE not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
