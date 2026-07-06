from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.access import ProductStatus, ProjectWorkspace
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.qc import ProductIndexRecord, QcChecklistItem, QcDecisionStatus
from coeus.domain.state_machine import can_transition
from coeus.domain.store import (
    StoreAsset,
    StoreProduct,
    StoreProductMetadata,
    object_key_segment,
)
from coeus.domain.tickets import DraftProductAsset, DraftProductVersion, TicketRecord
from coeus.repositories.access import SeedAccessRepository
from coeus.repositories.store import new_store_product_id
from coeus.services.analyst_records import approved_route
from coeus.services.audit import AuditLog
from coeus.services.qc_acg_policy import validate_qc_acg_assignment
from coeus.services.qc_records import (
    checklist_items,
    indexed_product,
    preview_kind,
    qc_decision,
    queued_index,
)
from coeus.services.store import StoreServices
from coeus.services.ticket_records import timeline
from coeus.services.tickets import TicketServices

QC_READ_PERMISSIONS = frozenset({Permission.QC_REVIEW})


@dataclass(frozen=True)
class QcApprovalInput:
    checklist: dict[str, bool]
    classification_level: int
    releasability: tuple[str, ...]
    handling_caveats: tuple[str, ...]
    acg_ids: frozenset[UUID]
    reason: str


class ReleaseCheckService:
    def __init__(self, access_repository: SeedAccessRepository) -> None:
        self._access = access_repository

    def approval_checklist(self, answers: dict[str, bool]) -> tuple[QcChecklistItem, ...]:
        checklist = checklist_items(answers)
        if not all(item.passed for item in checklist):
            raise AppError(409, "qc_checklist_incomplete", "Complete every QC checklist item.")
        return checklist

    def validate_release_metadata(self, approval: QcApprovalInput) -> None:
        if not approval.releasability:
            raise AppError(409, "releasability_required", "Releasability must be confirmed.")
        if not approval.handling_caveats:
            raise AppError(409, "handling_caveats_required", "Handling caveats are required.")
        if not approval.acg_ids:
            raise AppError(409, "product_acg_required", "At least one ACG must be confirmed.")
        for acg_id in approval.acg_ids:
            acg = self._access.get_acg(acg_id)
            if acg is None or not acg.is_active:
                raise AppError(409, "product_acg_required", "Products must use active ACGs.")


class ProductAutoIngestionService:
    def __init__(self, store: StoreServices, access_repository: SeedAccessRepository) -> None:
        self._store = store
        self._access = access_repository

    def ingest(
        self, actor: UserAccount, ticket: TicketRecord, approval: QcApprovalInput
    ) -> StoreProduct:
        self._require(actor, Permission.PRODUCT_CREATE_FROM_QC)
        draft = _latest_draft(ticket)
        project = self._project_for_ticket(ticket)
        project_acg_ids: frozenset[UUID] = project.acg_ids if project else frozenset()
        validate_qc_acg_assignment(self._access, actor, approval.acg_ids, project_acg_ids)
        acg_ids = approval.acg_ids | project_acg_ids
        now = datetime.now(UTC)
        product = StoreProduct(
            product_id=new_store_product_id(),
            reference=self._store.repository.next_reference(),
            metadata=StoreProductMetadata(
                title=draft.title,
                summary=draft.summary,
                description=draft.content,
                product_type=draft.product_type,
                source_type="qc_approved_draft",
                owner_team=_owner_team(ticket),
                area_or_region=ticket.intake.area_or_region or "Not specified",
                classification_level=approval.classification_level,
                releasability=frozenset(approval.releasability),
                handling_caveats=frozenset(approval.handling_caveats),
                tags=frozenset({"mock", "qc-approved", ticket.reference.casefold()}),
                acg_ids=acg_ids,
                project_id=project.project_id if project else None,
                # Held as draft until the route manager performs final release.
                status=ProductStatus.DRAFT,
                time_period_start=ticket.intake.time_period_start,
                time_period_end=ticket.intake.time_period_end,
                geojson_ref=None,
                bounding_box=None,
            ),
            assets=tuple(_store_asset(ticket.ticket_id, asset) for asset in draft.assets),
            created_by_user_id=actor.user_id,
            created_at=now,
            updated_at=now,
        )
        if not product.assets:
            raise AppError(409, "asset_required", "Approved products must include an asset.")
        self._store.repository.save_product(product)
        return product

    def _project_for_ticket(self, ticket: TicketRecord) -> ProjectWorkspace | None:
        for project in self._access.list_projects():
            if (
                ticket.ticket_id in project.ticket_ids
                or project.requester_user_id == ticket.requester_user_id
            ):
                return project
        return None

    @staticmethod
    def _require(actor: UserAccount, permission: Permission) -> None:
        if permission not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")


class ProductIndexingService:
    def index_product(
        self, ticket: TicketRecord, product: StoreProduct
    ) -> tuple[ProductIndexRecord, ...]:
        return (
            queued_index(ticket.ticket_id, product.product_id),
            indexed_product(ticket.ticket_id, product.product_id),
        )


class QualityControlService:
    def __init__(
        self,
        tickets: TicketServices,
        release_checks: ReleaseCheckService,
        ingestion: ProductAutoIngestionService,
        indexing: ProductIndexingService,
        audit_log: AuditLog,
    ) -> None:
        self._tickets = tickets
        self._release_checks = release_checks
        self._ingestion = ingestion
        self._indexing = indexing
        self._audit_log = audit_log

    def queue(self, actor: UserAccount) -> tuple[TicketRecord, ...]:
        self._require(actor, Permission.QC_REVIEW)
        return tuple(
            ticket
            for ticket in self._tickets.tickets.list_workflow_tickets(actor, QC_READ_PERMISSIONS)
            if ticket.state == TicketState.QC_REVIEW
        )

    def details(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        self._require(actor, Permission.QC_REVIEW)
        ticket = self._tickets.tickets.get_workflow_ticket(actor, ticket_id, QC_READ_PERMISSIONS)
        if ticket.state not in {
            TicketState.QC_REVIEW,
            TicketState.MANAGER_RELEASE,
            TicketState.DISSEMINATION_READY,
            TicketState.REWORK_REQUIRED,
        }:
            raise AppError(404, "product_not_found", "QC product was not found.")
        return ticket

    def approve(
        self, actor: UserAccount, ticket_id: UUID, approval: QcApprovalInput
    ) -> TicketRecord:
        self._require(actor, Permission.QC_APPROVE)
        ticket = self.details(actor, ticket_id)
        self._ensure_state(ticket, TicketState.QC_REVIEW)
        draft = _latest_draft(ticket)
        if draft.created_by_user_id == actor.user_id:
            raise AppError(403, "separation_of_duties", "Drafters cannot approve their own work.")
        checklist = self._release_checks.approval_checklist(approval.checklist)
        self._release_checks.validate_release_metadata(approval)
        product = self._ingestion.ingest(actor, ticket, approval)
        index_records = self._indexing.index_product(ticket, product)
        decision = qc_decision(
            ticket.ticket_id,
            QcDecisionStatus.APPROVED,
            approval.reason,
            actor.user_id,
            checklist,
        )
        self._ensure_transition(ticket.state, TicketState.MANAGER_RELEASE)
        updated = self._tickets.tickets.save_system_update(
            replace(
                ticket,
                state=TicketState.MANAGER_RELEASE,
                qc_decisions=(*ticket.qc_decisions, decision),
                product_index_records=(*ticket.product_index_records, *index_records),
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "qc_approved", product.reference),
                    timeline(
                        ticket.ticket_id, actor.user_id, "product_auto_ingested", product.reference
                    ),
                    timeline(
                        ticket.ticket_id,
                        actor.user_id,
                        "sent_for_manager_release",
                        "Awaiting final release by the route manager.",
                    ),
                ),
            )
        )
        self._audit_log.record(
            "qc_approved",
            str(actor.user_id),
            {"ticket_id": str(ticket_id), "product_id": str(product.product_id)},
        )
        return updated

    def reject(self, actor: UserAccount, ticket_id: UUID, reason: str) -> TicketRecord:
        self._require(actor, Permission.QC_REJECT)
        ticket = self.details(actor, ticket_id)
        self._ensure_state(ticket, TicketState.QC_REVIEW)
        checklist = checklist_items({})
        decision = qc_decision(
            ticket.ticket_id, QcDecisionStatus.REJECTED, reason, actor.user_id, checklist
        )
        self._ensure_transition(ticket.state, TicketState.REWORK_REQUIRED)
        updated = self._tickets.tickets.save_system_update(
            replace(
                ticket,
                state=TicketState.REWORK_REQUIRED,
                qc_decisions=(*ticket.qc_decisions, decision),
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "qc_rejected", reason),
                ),
            )
        )
        self._audit_log.record("qc_rejected", str(actor.user_id), {"ticket_id": str(ticket_id)})
        return updated

    @staticmethod
    def _require(actor: UserAccount, permission: Permission) -> None:
        if permission not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")

    @staticmethod
    def _ensure_state(ticket: TicketRecord, expected: TicketState) -> None:
        if ticket.state != expected:
            raise AppError(409, "invalid_ticket_state", "Ticket is not awaiting QC review.")

    @staticmethod
    def _ensure_transition(current: TicketState, target: TicketState) -> None:
        if not can_transition(current, target):
            raise AppError(409, "invalid_ticket_state", "Ticket cannot move to that state.")


def build_quality_control_service(
    tickets: TicketServices,
    store: StoreServices,
    access_repository: SeedAccessRepository,
    audit_log: AuditLog,
) -> QualityControlService:
    return QualityControlService(
        tickets,
        ReleaseCheckService(access_repository),
        ProductAutoIngestionService(store, access_repository),
        ProductIndexingService(),
        audit_log,
    )


def _latest_draft(ticket: TicketRecord) -> DraftProductVersion:
    if not ticket.draft_products:
        raise AppError(409, "draft_required", "A draft product is required before QC.")
    return ticket.draft_products[-1]


def _store_asset(ticket_id: UUID, asset: DraftProductAsset) -> StoreAsset:
    return StoreAsset(
        asset_id=uuid4(),
        name=asset.name,
        asset_type=asset.asset_type,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        sha256=asset.sha256,
        object_key=f"store/qc/{ticket_id}/{asset.asset_id}/{object_key_segment(asset.name)}",
        preview_kind=preview_kind(asset.mime_type, asset.asset_type),
    )


def _owner_team(ticket: TicketRecord) -> str:
    route = approved_route(ticket)
    if route is None:
        return "RFA"
    return "Collection" if route.value == "cm" else "RFA"
