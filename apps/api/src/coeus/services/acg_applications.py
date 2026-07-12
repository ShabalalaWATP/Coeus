from dataclasses import replace
from datetime import UTC, datetime
from math import ceil
from threading import RLock
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.access import (
    AccessControlGroup,
    AcgAccessApplication,
    AcgApplicationStatus,
)
from coeus.domain.auth import UserAccount
from coeus.repositories.access import AccessRepository
from coeus.repositories.acg_applications import AcgApplicationRepository
from coeus.services.audit import AuditLog

MAX_ACG_ADMINS = 8


class AcgApplicationService:
    def __init__(
        self,
        access: AccessRepository,
        workflows: AcgApplicationRepository,
        audit_log: AuditLog,
    ) -> None:
        self._access = access
        self._workflows = workflows
        self._audit_log = audit_log
        self._lock = RLock()
        self._bootstrap_owners()

    def catalogue(
        self, actor: UserAccount, page: int, page_size: int
    ) -> tuple[tuple[AccessControlGroup, ...], int, int]:
        self._require_active(actor)
        active = tuple(acg for acg in self._access.list_acgs() if acg.is_active)
        start = (page - 1) * page_size
        return active[start : start + page_size], len(active), _total_pages(active, page_size)

    def own_application(self, actor: UserAccount, acg_id: UUID) -> AcgAccessApplication | None:
        return self._workflows.get_for_user(acg_id, actor.user_id)

    def is_member(self, actor: UserAccount, acg_id: UUID) -> bool:
        return acg_id in self._access.acg_ids_for_user(actor.user_id)

    def can_review(self, actor: UserAccount, acg_id: UUID) -> bool:
        return self._is_platform_admin(actor) or self._workflows.is_admin(acg_id, actor.user_id)

    def submit(self, actor: UserAccount, acg_id: UUID, justification: str) -> AcgAccessApplication:
        with self._lock:
            self._require_active(actor)
            justification = justification.strip()
            if len(justification) < 10 or len(justification) > 500:
                raise AppError(422, "invalid_justification", "Justification is invalid.")
            acg = self._active_acg(acg_id)
            if self.is_member(actor, acg.acg_id):
                raise AppError(409, "acg_already_member", "The user is already an ACG member.")
            existing = self.own_application(actor, acg.acg_id)
            if existing is not None and existing.status == AcgApplicationStatus.PENDING:
                raise AppError(
                    409, "acg_application_pending", "A pending application already exists."
                )
            application = AcgAccessApplication(
                application_id=uuid4(),
                acg_id=acg.acg_id,
                applicant_user_id=actor.user_id,
                justification=justification,
                status=AcgApplicationStatus.PENDING,
                submitted_at=datetime.now(UTC),
            )
            snapshot = self._workflows.snapshot()
            self._workflows.save(application)
            try:
                self._audit_log.record(
                    "acg_application_submitted",
                    str(actor.user_id),
                    {"acg_id": str(acg.acg_id), "application_id": str(application.application_id)},
                )
            except Exception:
                self._workflows.restore(snapshot)
                raise
            return application

    def withdraw(self, actor: UserAccount, acg_id: UUID) -> AcgAccessApplication:
        with self._lock:
            application = self._owned_pending(actor, acg_id)
            snapshot = self._workflows.snapshot()
            withdrawn = replace(application, status=AcgApplicationStatus.WITHDRAWN)
            self._workflows.save(withdrawn)
            try:
                self._audit_log.record(
                    "acg_application_withdrawn",
                    str(actor.user_id),
                    {
                        "acg_id": str(acg_id),
                        "application_id": str(application.application_id),
                    },
                )
            except Exception:
                self._workflows.restore(snapshot)
                raise
            return withdrawn

    def review_queue(
        self, actor: UserAccount, page: int, page_size: int
    ) -> tuple[tuple[AcgAccessApplication, ...], int, int]:
        self._require_active(actor)
        reviewable = self._reviewable_acg_ids(actor)
        pending = self._workflows.list_pending(reviewable)
        start = (page - 1) * page_size
        return pending[start : start + page_size], len(pending), _total_pages(pending, page_size)

    def decide(
        self,
        actor: UserAccount,
        application_id: UUID,
        decision: AcgApplicationStatus,
        reason: str | None,
    ) -> AcgAccessApplication:
        with self._lock:
            self._require_active(actor)
            application = self._workflows.get_by_id(application_id)
            if application is None:
                raise AppError(404, "acg_application_not_found", "Application was not found.")
            if not self.can_review(actor, application.acg_id):
                raise AppError(404, "acg_application_not_found", "Application was not found.")
            if application.applicant_user_id == actor.user_id:
                raise AppError(
                    403, "acg_self_decision", "Users cannot decide their own application."
                )
            if application.status != AcgApplicationStatus.PENDING:
                raise AppError(409, "acg_application_stale", "Application is no longer pending.")
            if decision == AcgApplicationStatus.REJECTED and (
                not reason or len(reason.strip()) < 3
            ):
                raise AppError(422, "decision_reason_required", "A rejection reason is required.")
            if decision == AcgApplicationStatus.APPROVED:
                self._active_acg(application.acg_id)
                if application.acg_id in self._access.acg_ids_for_user(
                    application.applicant_user_id
                ):
                    raise AppError(409, "acg_already_member", "The user is already an ACG member.")
            return self._apply_decision(actor, application, decision, reason)

    def list_admins(self, actor: UserAccount, acg_id: UUID) -> tuple[UserAccount, ...]:
        self._require_platform_admin(actor)
        self._get_acg(acg_id)
        users = (
            self._access.get_user(user_id) for user_id in self._workflows.admin_user_ids(acg_id)
        )
        return tuple(
            sorted((user for user in users if user is not None), key=lambda u: u.display_name)
        )

    def add_admin(self, actor: UserAccount, acg_id: UUID, user_id: UUID) -> tuple[UserAccount, ...]:
        with self._lock:
            self._require_platform_admin(actor)
            self._get_acg(acg_id)
            self._active_user(user_id)
            current = self._workflows.admin_user_ids(acg_id)
            if user_id in current:
                raise AppError(409, "acg_admin_exists", "The user already administers this ACG.")
            unique_ids = current | {user_id}
            if len(unique_ids) > MAX_ACG_ADMINS:
                raise AppError(
                    409, "acg_admin_limit", "An ACG can have at most eight administrators."
                )
            snapshot = self._workflows.snapshot()
            self._workflows.replace_admins(acg_id, unique_ids)
            try:
                self._audit_log.record(
                    "acg_administrator_added",
                    str(actor.user_id),
                    {"acg_id": str(acg_id), "user_id": str(user_id)},
                )
            except Exception:
                self._workflows.restore(snapshot)
                raise
            return self.list_admins(actor, acg_id)

    def remove_admin(
        self, actor: UserAccount, acg_id: UUID, user_id: UUID
    ) -> tuple[UserAccount, ...]:
        with self._lock:
            self._require_platform_admin(actor)
            acg = self._get_acg(acg_id)
            current = self._workflows.admin_user_ids(acg_id)
            if user_id not in current:
                raise AppError(409, "acg_admin_not_found", "The user is not an ACG administrator.")
            if acg.is_active and len(current) == 1:
                raise AppError(
                    409,
                    "acg_admin_required",
                    "An active ACG must retain at least one administrator.",
                )
            snapshot = self._workflows.snapshot()
            self._workflows.replace_admins(acg_id, current - {user_id})
            try:
                self._audit_log.record(
                    "acg_administrator_removed",
                    str(actor.user_id),
                    {"acg_id": str(acg_id), "user_id": str(user_id)},
                )
            except Exception:
                self._workflows.restore(snapshot)
                raise
            return self.list_admins(actor, acg_id)

    def active_user_directory(
        self, actor: UserAccount, query: str, page: int, page_size: int
    ) -> tuple[tuple[UserAccount, ...], int, int]:
        self._require_directory_access(actor)
        needle = query.strip().casefold()
        users = tuple(
            sorted(
                (
                    user
                    for user in self._access.list_users()
                    if user.is_active
                    and (
                        not needle
                        or needle in user.display_name.casefold()
                        or needle in user.username.casefold()
                    )
                ),
                key=lambda user: (user.display_name.casefold(), user.username.casefold()),
            )
        )
        start = (page - 1) * page_size
        return users[start : start + page_size], len(users), _total_pages(users, page_size)

    def _apply_decision(
        self,
        actor: UserAccount,
        application: AcgAccessApplication,
        decision: AcgApplicationStatus,
        reason: str | None,
    ) -> AcgAccessApplication:
        snapshot = self._workflows.snapshot()
        decided = replace(
            application,
            status=decision,
            decided_at=datetime.now(UTC),
            decided_by_user_id=actor.user_id,
            decision_reason=reason.strip() if reason else None,
        )
        membership_added = False
        try:
            self._workflows.save(decided)
            if decision == AcgApplicationStatus.APPROVED:
                self._access.add_membership(application.acg_id, application.applicant_user_id)
                membership_added = True
            self._audit_log.record(
                "acg_application_decided",
                str(actor.user_id),
                {
                    "acg_id": str(application.acg_id),
                    "application_id": str(application.application_id),
                    "applicant_user_id": str(application.applicant_user_id),
                    "decision": decision.value,
                },
            )
        except Exception:
            if membership_added:
                try:
                    self._access.remove_membership(
                        application.acg_id, application.applicant_user_id
                    )
                finally:
                    self._workflows.restore(snapshot)
            else:
                self._workflows.restore(snapshot)
            raise
        return decided

    def _reviewable_acg_ids(self, actor: UserAccount) -> frozenset[UUID]:
        if self._is_platform_admin(actor):
            return frozenset(acg.acg_id for acg in self._access.list_acgs())
        return frozenset(
            acg.acg_id
            for acg in self._access.list_acgs()
            if self._workflows.is_admin(acg.acg_id, actor.user_id)
        )

    def _owned_pending(self, actor: UserAccount, acg_id: UUID) -> AcgAccessApplication:
        application = self.own_application(actor, acg_id)
        if application is None:
            raise AppError(404, "acg_application_not_found", "Application was not found.")
        if application.status != AcgApplicationStatus.PENDING:
            raise AppError(409, "acg_application_stale", "Application is no longer pending.")
        return application

    def _active_acg(self, acg_id: UUID) -> AccessControlGroup:
        acg = self._get_acg(acg_id)
        if not acg.is_active:
            raise AppError(409, "acg_inactive", "The ACG is inactive.")
        return acg

    def _get_acg(self, acg_id: UUID) -> AccessControlGroup:
        acg = self._access.get_acg(acg_id)
        if acg is None:
            raise AppError(404, "acg_not_found", "Access control group was not found.")
        return acg

    def _active_user(self, user_id: UUID) -> UserAccount:
        user = self._access.get_user(user_id)
        if user is None or not user.is_active:
            raise AppError(422, "active_user_required", "ACG administrators must be active users.")
        return user

    def _bootstrap_owners(self) -> None:
        for acg in self._access.list_acgs():
            if acg.owner_user_id is None:
                continue
            owner = self._access.get_user(acg.owner_user_id)
            if owner is None or not owner.is_active:
                continue
            if not self._workflows.is_initialised(acg.acg_id):
                self._workflows.replace_admins(acg.acg_id, frozenset({owner.user_id}))

    @staticmethod
    def _require_active(actor: UserAccount) -> None:
        if not actor.is_active:
            raise AppError(403, "inactive_user", "The user account is inactive.")

    @classmethod
    def _require_platform_admin(cls, actor: UserAccount) -> None:
        cls._require_active(actor)
        if not cls._is_platform_admin(actor):
            raise AppError(403, "forbidden", "Permission denied.")

    @classmethod
    def _require_directory_access(cls, actor: UserAccount) -> None:
        cls._require_active(actor)
        if not (cls._is_platform_admin(actor) or Permission.ACG_ASSIGN_USER in actor.permissions):
            raise AppError(403, "forbidden", "Permission denied.")

    @staticmethod
    def _is_platform_admin(actor: UserAccount) -> bool:
        return Permission.SYSTEM_CONFIGURE in actor.permissions


def _total_pages(items: tuple[object, ...], page_size: int) -> int:
    return ceil(len(items) / page_size) if items else 0
