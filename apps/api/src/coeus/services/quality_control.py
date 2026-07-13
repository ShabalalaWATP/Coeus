from contextlib import suppress
from dataclasses import replace
from uuid import UUID

from coeus.application.ports.workflow_transaction import WorkflowTransactionPort
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.qc import ProductIndexRecord, QcChecklistItem, QcDecisionStatus
from coeus.domain.state_machine import can_transition
from coeus.domain.store import StoreProduct, normalise_synthetic_release_markers
from coeus.domain.tickets import TicketRecord
from coeus.repositories.access import AccessRepository
from coeus.services.audit import AuditLog
from coeus.services.notifications import NotificationService
from coeus.services.object_storage import ObjectStorage
from coeus.services.prioritisation import priority_sort_key
from coeus.services.qc_ingestion import (
    ProductAutoIngestionService,
    QcApprovalInput,
    latest_draft,
)
from coeus.services.qc_records import (
    checklist_items,
    indexed_product,
    qc_decision,
    queued_index,
)
from coeus.services.qc_release import QcReleaseStep, release_target_state
from coeus.services.store import StoreServices
from coeus.services.ticket_records import timeline
from coeus.services.tickets import TicketServices

__all__ = ["QcApprovalInput", "QualityControlService", "ReleaseCheckService"]

QC_READ_PERMISSIONS = frozenset({Permission.QC_REVIEW})


class ReleaseCheckService:
    def __init__(self, access_repository: AccessRepository) -> None:
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
        try:
            normalise_synthetic_release_markers(approval.releasability, approval.handling_caveats)
        except ValueError as exc:
            raise AppError(
                409,
                "release_markers_unsupported",
                "Only synthetic release markers are supported.",
            ) from exc
        if not approval.acg_ids:
            raise AppError(409, "product_acg_required", "At least one ACG must be confirmed.")
        for acg_id in approval.acg_ids:
            acg = self._access.get_acg(acg_id)
            if acg is None or not acg.is_active:
                raise AppError(409, "product_acg_required", "Products must use active ACGs.")


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
        release: QcReleaseStep,
        audit_log: AuditLog,
    ) -> None:
        self._tickets = tickets
        self._release_checks = release_checks
        self._ingestion = ingestion
        self._indexing = indexing
        self._release = release
        self._audit_log = audit_log

    def queue(self, actor: UserAccount) -> tuple[TicketRecord, ...]:
        self._require(actor, Permission.QC_REVIEW)
        queued = (
            ticket
            for ticket in self._tickets.tickets.list_workflow_tickets(actor, QC_READ_PERMISSIONS)
            if ticket.state == TicketState.QC_REVIEW
        )
        return tuple(sorted(queued, key=priority_sort_key))

    def details(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        self._require(actor, Permission.QC_REVIEW)
        ticket = self._tickets.tickets.get_workflow_ticket(actor, ticket_id, QC_READ_PERMISSIONS)
        if ticket.state not in {
            TicketState.QC_REVIEW,
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
        draft = latest_draft(ticket)
        if draft.created_by_user_id == actor.user_id:
            raise AppError(403, "separation_of_duties", "Drafters cannot approve their own work.")
        # Validate everything up front so a failure can never leave an orphaned
        # DRAFT product without a matching QC decision on the ticket.
        checklist = self._release_checks.approval_checklist(approval.checklist)
        self._release_checks.validate_release_metadata(approval)
        self._ensure_transition(ticket.state, release_target_state(ticket))
        product = self._ingestion.ingest(actor, ticket, approval)
        try:
            index_records = self._indexing.index_product(ticket, product)
            decision = qc_decision(
                ticket.ticket_id,
                QcDecisionStatus.APPROVED,
                approval.reason,
                actor.user_id,
                checklist,
            )
            pending = replace(
                ticket,
                qc_decisions=(*ticket.qc_decisions, decision),
                product_index_records=(*ticket.product_index_records, *index_records),
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "qc_approved", product.reference),
                    timeline(
                        ticket.ticket_id,
                        actor.user_id,
                        "product_auto_ingested",
                        product.reference,
                    ),
                ),
            )
            outcome = self._release.complete(actor, ticket, pending, product)
            # One durable success event avoids a partially written audit trail
            # claiming approval when a second append fails and release is
            # compensated.
            if not outcome.audit_committed:
                self._audit_log.record(
                    outcome.audit_event,
                    str(actor.user_id),
                    {
                        "ticket_id": str(ticket_id),
                        "product_id": str(product.product_id),
                        "qc_approved": "true",
                    },
                )
        except Exception:
            # The release step, ticket update or audit failed after ingestion;
            # restore the original workflow state and remove the product so
            # approval can be retried without an orphaned DRAFT product. If
            # persistence itself is down the restore may also fail; the
            # product discard must still run so no orphan survives.
            if "outcome" in locals():
                with suppress(Exception):
                    self._tickets.tickets.restore_system_update_if_current(outcome.ticket, ticket)
            self._ingestion.discard(product.product_id)
            raise
        if not outcome.audit_committed:
            self._release.notify_best_effort(actor, outcome)
        return outcome.ticket

    def reject(self, actor: UserAccount, ticket_id: UUID, reason: str) -> TicketRecord:
        self._require(actor, Permission.QC_REJECT)
        ticket = self.details(actor, ticket_id)
        self._ensure_state(ticket, TicketState.QC_REVIEW)
        checklist = checklist_items({})
        decision = qc_decision(
            ticket.ticket_id, QcDecisionStatus.REJECTED, reason, actor.user_id, checklist
        )
        self._ensure_transition(ticket.state, TicketState.REWORK_REQUIRED)
        updated = self._tickets.tickets.save_system_update_if_current(
            ticket,
            replace(
                ticket,
                state=TicketState.REWORK_REQUIRED,
                qc_decisions=(*ticket.qc_decisions, decision),
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "qc_rejected", reason),
                ),
            ),
        )
        try:
            self._audit_log.record("qc_rejected", str(actor.user_id), {"ticket_id": str(ticket_id)})
        except Exception:
            self._tickets.tickets.restore_system_update_if_current(updated, ticket)
            raise
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
    access_repository: AccessRepository,
    audit_log: AuditLog,
    storage: ObjectStorage,
    notifications: NotificationService,
    transaction: WorkflowTransactionPort | None = None,
) -> QualityControlService:
    return QualityControlService(
        tickets,
        ReleaseCheckService(access_repository),
        ProductAutoIngestionService(store, access_repository, storage),
        ProductIndexingService(),
        QcReleaseStep(
            tickets,
            store,
            access_repository,
            notifications,
            audit_log,
            transaction,
        ),
        audit_log,
    )
