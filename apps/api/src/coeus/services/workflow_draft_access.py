"""Live object policy and byte boundary for protected workflow drafts."""

from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from coeus.application.ports.access import ActiveAcgReader
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.product_submission import DraftProductAsset, DraftProductVersion
from coeus.domain.tickets import TicketRecord
from coeus.repositories.teams import TeamRepository
from coeus.services.analyst_records import approved_route, assigned_to
from coeus.services.manager_scope import require_route_manager, require_valid_assignment_team
from coeus.services.object_storage import ObjectStorage
from coeus.services.tickets import TicketServices


@dataclass(frozen=True)
class DraftPreview:
    asset: DraftProductAsset
    content: bytes


class WorkflowDraftAccessPolicy:
    def __init__(self, access: ActiveAcgReader, teams: TeamRepository) -> None:
        self._access = access
        self._teams = teams

    def require_ticket_content(self, actor: UserAccount, ticket: TicketRecord) -> None:
        for version in ticket.draft_products:
            self.require_version(actor, ticket, version)

    def require_version(
        self, actor: UserAccount, ticket: TicketRecord, version: DraftProductVersion
    ) -> None:
        if not self._has_base_authority(actor, version):
            raise _not_found()
        if self._is_assigned_analyst(actor, ticket):
            return
        if self._is_responsible_manager(actor, ticket):
            return
        if self._is_named_qc_reviewer(actor, ticket):
            return
        raise _not_found()

    def _has_base_authority(self, actor: UserAccount, version: DraftProductVersion) -> bool:
        if (
            not actor.is_active
            or Permission.PRODUCT_READ not in actor.permissions
            or actor.clearance_level < version.classification_level
        ):
            return False
        if not version.acg_ids:
            return True
        actor_acgs = self._access.active_acg_ids_for_user(actor.user_id)
        return bool(actor_acgs.intersection(version.acg_ids))

    @staticmethod
    def _is_assigned_analyst(actor: UserAccount, ticket: TicketRecord) -> bool:
        return bool(
            RoleName.INTELLIGENCE_ANALYST in actor.roles
            and Permission.ANALYST_WORK in actor.permissions
            and assigned_to(ticket, actor.user_id)
            and ticket.state
            in {
                TicketState.ANALYST_IN_PROGRESS,
                TicketState.MANAGER_APPROVAL,
                TicketState.QC_REVIEW,
                TicketState.REWORK_REQUIRED,
            }
        )

    def _is_responsible_manager(self, actor: UserAccount, ticket: TicketRecord) -> bool:
        if ticket.state != TicketState.MANAGER_APPROVAL:
            return False
        route = approved_route(ticket)
        if route is None or Permission.PRODUCT_APPROVE not in actor.permissions:
            return False
        try:
            require_route_manager(actor, route)
            require_valid_assignment_team(ticket, route, self._teams)
        except AppError:
            return False
        return True

    @staticmethod
    def _is_named_qc_reviewer(actor: UserAccount, ticket: TicketRecord) -> bool:
        return bool(
            RoleName.QUALITY_CONTROL_MANAGER in actor.roles
            and Permission.QC_REVIEW in actor.permissions
            and ticket.qc_reviewer_user_id == actor.user_id
            and ticket.state in {TicketState.QC_REVIEW, TicketState.REWORK_REQUIRED}
        )


class WorkflowDraftAccessService:
    def __init__(
        self,
        tickets: TicketServices,
        policy: WorkflowDraftAccessPolicy,
        storage: ObjectStorage,
    ) -> None:
        self._tickets = tickets
        self._policy = policy
        self._storage = storage

    def preview(
        self, actor: UserAccount, ticket_id: UUID, version_id: UUID, asset_id: UUID
    ) -> DraftPreview:
        ticket = self._tickets.tickets.get_workflow_ticket(
            actor,
            ticket_id,
            frozenset(
                {
                    Permission.ANALYST_WORK,
                    Permission.PRODUCT_APPROVE,
                    Permission.QC_REVIEW,
                }
            ),
        )
        version = next(
            (item for item in ticket.draft_products if item.version_id == version_id), None
        )
        asset = (
            next((item for item in version.assets if item.asset_id == asset_id), None)
            if version
            else None
        )
        if version is None or asset is None:
            raise _not_found()
        self._policy.require_version(actor, ticket, version)
        if not asset.object_key or not self._storage.exists(asset.object_key):
            raise _not_found()
        content = self._storage.read_bytes(asset.object_key)
        if len(content) != asset.size_bytes or sha256(content).hexdigest() != asset.sha256:
            raise AppError(
                409, "submission_asset_integrity_failed", "Product asset integrity failed."
            )
        return DraftPreview(asset=asset, content=content)


def _not_found() -> AppError:
    return AppError(404, "submission_not_found", "Product submission was not found.")
