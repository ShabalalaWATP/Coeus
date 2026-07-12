from dataclasses import dataclass
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.access import (
    AccessCheck,
    AccessControlGroup,
    AccessDecision,
    ProductRecord,
    ProductStatus,
)
from coeus.domain.auth import UserAccount
from coeus.repositories.access import AccessRepository
from coeus.repositories.acg_applications import AcgApplicationRepository
from coeus.services.acg_applications import AcgApplicationService
from coeus.services.audit import AuditLog


class AccessControlGroupService:
    def __init__(
        self,
        repository: AccessRepository,
        audit_log: AuditLog,
        workflows: AcgApplicationRepository,
    ) -> None:
        self._repository = repository
        self._audit_log = audit_log
        self._workflows = workflows

    def list_visible_acgs(self, user: UserAccount) -> tuple[AccessControlGroup, ...]:
        if Permission.ACG_VIEW not in user.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
        if _can_administer_acgs(user):
            return self._repository.list_acgs()
        user_acg_ids = self._repository.active_acg_ids_for_user(user.user_id)
        return tuple(acg for acg in self._repository.list_acgs() if acg.acg_id in user_acg_ids)

    def get_visible_acg(self, user: UserAccount, acg_id: UUID) -> AccessControlGroup:
        acg = self._get_acg(acg_id)
        if acg not in self.list_visible_acgs(user):
            raise AppError(404, "acg_not_found", "Access control group was not found.")
        return acg

    def create_acg(
        self,
        actor: UserAccount,
        code: str,
        name: str,
        description: str,
        owner_user_id: UUID | None = None,
    ) -> AccessControlGroup:
        self._require(actor, Permission.ACG_CREATE)
        if any(existing.code == code for existing in self._repository.list_acgs()):
            raise AppError(409, "acg_code_exists", "An ACG already uses this code.")
        initial_admin_id = owner_user_id or actor.user_id
        initial_admin = self._repository.get_user(initial_admin_id)
        if initial_admin is None or not initial_admin.is_active:
            raise AppError(422, "active_user_required", "The ACG owner must be an active user.")
        acg = AccessControlGroup(
            acg_id=uuid4(),
            code=code,
            name=name,
            description=description,
            owner_user_id=owner_user_id,
            is_active=True,
        )
        workflow_snapshot = self._workflows.snapshot()
        self._repository.save_acg(acg)
        try:
            self._workflows.replace_admins(acg.acg_id, frozenset({initial_admin_id}))
            self._audit_log.record(
                "acg_created",
                str(actor.user_id),
                {
                    "acg_id": str(acg.acg_id),
                    "code": acg.code,
                    "initial_admin_user_id": str(initial_admin_id),
                },
            )
        except Exception:
            try:
                self._repository.delete_acg(acg.acg_id)
            finally:
                self._workflows.restore(workflow_snapshot)
            raise
        return acg

    def update_acg(
        self,
        actor: UserAccount,
        acg_id: UUID,
        name: str | None = None,
        description: str | None = None,
        is_active: bool | None = None,
    ) -> AccessControlGroup:
        self._require(actor, Permission.ACG_UPDATE)
        acg = self._get_acg(acg_id)
        updated = AccessControlGroup(
            acg_id=acg.acg_id,
            code=acg.code,
            name=name if name is not None else acg.name,
            description=description if description is not None else acg.description,
            owner_user_id=acg.owner_user_id,
            is_active=is_active if is_active is not None else acg.is_active,
        )
        self._repository.save_acg(updated)
        try:
            self._audit_log.record(
                "acg_updated",
                str(actor.user_id),
                {"acg_id": str(acg_id)},
            )
        except Exception:
            self._repository.save_acg(acg)
            raise
        return updated

    def add_user(self, actor: UserAccount, acg_id: UUID, user_id: UUID) -> None:
        self._require(actor, Permission.ACG_ASSIGN_USER)
        acg = self._get_acg(acg_id)
        if not acg.is_active:
            raise AppError(409, "acg_inactive", "Members cannot be added to an inactive ACG.")
        if self._repository.get_user(user_id) is None:
            raise AppError(404, "user_not_found", "User was not found.")
        self._reject_non_admin_self_membership_change(actor, user_id)
        had_membership = acg_id in self._repository.acg_ids_for_user(user_id)
        self._repository.add_membership(acg_id, user_id)
        try:
            self._audit_log.record(
                "acg_membership_added",
                str(actor.user_id),
                {"acg_id": str(acg_id), "user_id": str(user_id)},
            )
        except Exception:
            if not had_membership:
                self._repository.remove_membership(acg_id, user_id)
            raise

    def remove_user(self, actor: UserAccount, acg_id: UUID, user_id: UUID) -> None:
        self._require(actor, Permission.ACG_ASSIGN_USER)
        self._get_acg(acg_id)
        self._reject_non_admin_self_membership_change(actor, user_id)
        had_membership = acg_id in self._repository.acg_ids_for_user(user_id)
        self._repository.remove_membership(acg_id, user_id)
        try:
            self._audit_log.record(
                "acg_membership_removed",
                str(actor.user_id),
                {"acg_id": str(acg_id), "user_id": str(user_id)},
            )
        except Exception:
            if had_membership:
                self._repository.add_membership(acg_id, user_id)
            raise

    def list_member_ids(self, acg_id: UUID) -> tuple[UUID, ...]:
        self._get_acg(acg_id)
        return tuple(
            membership.user_id for membership in self._repository.list_memberships_for_acg(acg_id)
        )

    def _get_acg(self, acg_id: UUID) -> AccessControlGroup:
        acg = self._repository.get_acg(acg_id)
        if acg is None:
            raise AppError(404, "acg_not_found", "Access control group was not found.")
        return acg

    @staticmethod
    def _require(user: UserAccount, permission: Permission) -> None:
        if permission not in user.permissions:
            raise AppError(403, "forbidden", "Permission denied.")

    @staticmethod
    def _reject_non_admin_self_membership_change(actor: UserAccount, user_id: UUID) -> None:
        if actor.user_id == user_id and Permission.SYSTEM_CONFIGURE not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")


def _can_administer_acgs(user: UserAccount) -> bool:
    return bool(
        {
            Permission.SYSTEM_CONFIGURE,
            Permission.ACG_CREATE,
            Permission.ACG_UPDATE,
            Permission.ACG_ASSIGN_USER,
            Permission.ACG_ASSIGN_PRODUCT,
        }.intersection(user.permissions)
    )


class ProductAccessPolicy:
    def __init__(self, repository: AccessRepository) -> None:
        self._repository = repository

    def evaluate(self, user: UserAccount, product: ProductRecord) -> AccessDecision:
        checks = [
            AccessCheck("active_user", user.is_active, "User account is active."),
            AccessCheck(
                "rbac_product_read",
                Permission.PRODUCT_READ in user.permissions,
                "User has product read permission.",
            ),
            AccessCheck(
                "product_status",
                product.status != ProductStatus.ARCHIVED,
                "Product is not archived.",
            ),
            AccessCheck(
                "clearance",
                user.clearance_level >= product.classification_level,
                "User clearance meets the product requirement.",
            ),
        ]
        if product.status == ProductStatus.DRAFT:
            checks.append(
                AccessCheck(
                    "draft_visibility",
                    Permission.PRODUCT_MANAGE_ASSETS in user.permissions,
                    "Draft products require product management permission.",
                )
            )
        user_acg_ids = self._repository.active_acg_ids_for_user(user.user_id)
        has_shared_acg = bool(user_acg_ids.intersection(product.acg_ids))
        checks.append(
            AccessCheck(
                "acg_membership",
                has_shared_acg,
                "User shares a product ACG.",
            )
        )
        allowed = all(check.passed for check in checks)
        return AccessDecision(
            allowed=allowed,
            reason="access_granted" if allowed else "access_denied",
            checks=tuple(checks),
        )


class AccessDiagnosticsService:
    def __init__(
        self,
        repository: AccessRepository,
        product_policy: ProductAccessPolicy,
    ) -> None:
        self._repository = repository
        self._product_policy = product_policy

    def diagnose_product(self, product_id: UUID, subject_user_id: UUID) -> AccessDecision:
        product = self._repository.get_product(product_id)
        if product is None:
            raise AppError(404, "product_not_found", "Product was not found.")
        subject = self._repository.get_user(subject_user_id)
        if subject is None:
            raise AppError(404, "user_not_found", "User was not found.")
        return self._product_policy.evaluate(subject, product)


@dataclass(frozen=True)
class AccessServices:
    repository: AccessRepository
    acgs: AccessControlGroupService
    product_policy: ProductAccessPolicy
    diagnostics: AccessDiagnosticsService
    applications: AcgApplicationService


def build_access_services(
    repository: AccessRepository,
    audit_log: AuditLog,
    application_repository: AcgApplicationRepository | None = None,
) -> AccessServices:
    product_policy = ProductAccessPolicy(repository)
    workflows = application_repository or AcgApplicationRepository()
    return AccessServices(
        repository=repository,
        acgs=AccessControlGroupService(repository, audit_log, workflows),
        product_policy=product_policy,
        diagnostics=AccessDiagnosticsService(repository, product_policy),
        applications=AcgApplicationService(repository, workflows, audit_log),
    )
