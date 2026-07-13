"""Final release performed at QC approval.

Quality Control now owns the release that the retired manager-release step
performed: publishing the product, recording dissemination and feedback,
and notifying the requester. For a collect the customer asked to have
analysed, QC instead forwards the ticket to RFA assignment with the collect
product linked for the analysts; the collect itself stays DRAFT and is never
released to the customer directly.
"""

from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from coeus.application.ports.workflow_transaction import WorkflowTransactionPort
from coeus.core.errors import AppError
from coeus.domain.access import ProductStatus
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.store import StoreProduct
from coeus.domain.tickets import (
    ManagerRoutingDecisionStatus,
    RoutingRoute,
    TicketRecord,
)
from coeus.domain.workflow_transaction import ReleaseNotificationIntent, WorkflowAuditIntent
from coeus.repositories.access import AccessRepository
from coeus.services.analyst_assignment import deactivate_route_assignments
from coeus.services.analyst_records import approved_route, linked_product_record
from coeus.services.audit import AuditLog
from coeus.services.notifications import NotificationService
from coeus.services.qc_records import dissemination, feedback_request
from coeus.services.routing_records import decision as routing_decision
from coeus.services.store import StoreServices
from coeus.services.ticket_records import timeline
from coeus.services.tickets import TicketServices

FORWARD_REASON = "Collect approved by QC; forwarded to RFA for the requested analysis."


def forwards_to_rfa(ticket: TicketRecord) -> bool:
    """An analysed collect returns to RFA assignment instead of releasing."""
    return approved_route(ticket) == RoutingRoute.CM and ticket.collect_disposition == "analysed"


def release_target_state(ticket: TicketRecord) -> TicketState:
    return (
        TicketState.ANALYST_ASSIGNMENT
        if forwards_to_rfa(ticket)
        else TicketState.DISSEMINATION_READY
    )


@dataclass(frozen=True)
class QcReleaseOutcome:
    ticket: TicketRecord
    product: StoreProduct
    audit_event: str
    # Set only when the product was released to a customer to notify.
    requester: UserAccount | None
    audit_committed: bool = False


class QcReleaseStep:
    """Applies the release outcome inside QC approval's compensation scope.

    The caller (QualityControlService.approve) records the audit events and,
    if anything raises, discards the ingested product and restores the
    original ticket; this step only builds and saves the updated records.
    """

    def __init__(
        self,
        tickets: TicketServices,
        store: StoreServices,
        access: AccessRepository,
        notifications: NotificationService,
        audit_log: AuditLog,
        transaction: WorkflowTransactionPort | None = None,
    ) -> None:
        self._tickets = tickets
        self._store = store
        self._access = access
        self._notifications = notifications
        self._audit_log = audit_log
        self._transaction = transaction

    def complete(
        self,
        actor: UserAccount,
        expected: TicketRecord,
        ticket: TicketRecord,
        product: StoreProduct,
    ) -> QcReleaseOutcome:
        """`ticket` carries the QC decision and index records but not yet the
        release outcome; the outcome's ticket has been saved."""
        if forwards_to_rfa(ticket):
            return self._forward_to_rfa(actor, expected, ticket, product)
        return self._release_to_customer(actor, expected, ticket, product)

    def _forward_to_rfa(
        self,
        actor: UserAccount,
        expected: TicketRecord,
        ticket: TicketRecord,
        product: StoreProduct,
    ) -> QcReleaseOutcome:
        decision = routing_decision(
            ticket.ticket_id,
            actor.user_id,
            RoutingRoute.RFA,
            ManagerRoutingDecisionStatus.APPROVED,
            FORWARD_REASON,
            None,
        )
        link = linked_product_record(
            ticket.ticket_id,
            product.product_id,
            product.reference,
            product.metadata.title,
            product.metadata.summary,
            actor.user_id,
        )
        proposed = replace(
            ticket,
            state=TicketState.ANALYST_ASSIGNMENT,
            manager_decisions=(*ticket.manager_decisions, decision),
            linked_products=(*ticket.linked_products, link),
            # The CM leg is complete: its assignments deactivate so the
            # collection analysts stop seeing the ticket as their task.
            analyst_assignments=deactivate_route_assignments(
                ticket.analyst_assignments, RoutingRoute.CM
            ),
            timeline=(
                *ticket.timeline,
                timeline(ticket.ticket_id, actor.user_id, "forwarded_to_rfa", FORWARD_REASON),
            ),
        )
        updated = self._commit_or_save(
            actor, expected, proposed, product, "collect_forwarded_to_rfa", None
        )
        return QcReleaseOutcome(
            ticket=updated,
            product=product,
            audit_event="collect_forwarded_to_rfa",
            requester=None,
            audit_committed=self._transaction is not None,
        )

    def _release_to_customer(
        self,
        actor: UserAccount,
        expected: TicketRecord,
        original_ticket: TicketRecord,
        original_product: StoreProduct,
    ) -> QcReleaseOutcome:
        requester = self._access.get_user(original_ticket.requester_user_id)
        if requester is None or not requester.is_active:
            raise AppError(409, "requester_not_active", "Requester must be active.")
        product = replace(
            original_product,
            metadata=replace(original_product.metadata, status=ProductStatus.PUBLISHED),
        )
        if not self._store.details.can_read_product(requester, product):
            raise AppError(404, "product_not_found", "Product was not found.")
        proposed = replace(
            original_ticket,
            state=TicketState.DISSEMINATION_READY,
            disseminations=(
                *original_ticket.disseminations,
                dissemination(original_ticket.ticket_id, product.product_id, requester.user_id),
            ),
            feedback_requests=(
                *original_ticket.feedback_requests,
                feedback_request(original_ticket.ticket_id, product.product_id, requester.user_id),
            ),
            timeline=(
                *original_ticket.timeline,
                timeline(
                    original_ticket.ticket_id,
                    actor.user_id,
                    "product_released",
                    product.reference,
                ),
                timeline(
                    original_ticket.ticket_id,
                    actor.user_id,
                    "product_disseminated",
                    product.reference,
                ),
                timeline(
                    original_ticket.ticket_id,
                    actor.user_id,
                    "customer_notified",
                    requester.username,
                ),
            ),
        )
        notification = ReleaseNotificationIntent(
            requester_user_id=requester.user_id,
            ticket_reference=original_ticket.reference,
            product_id=product.product_id,
            product_reference=product.reference,
            product_title=product.metadata.title,
        )
        if self._transaction is None:
            self._store.repository.save_product(product)
        updated = self._commit_or_save(
            actor, expected, proposed, product, "product_released", notification
        )
        return QcReleaseOutcome(
            ticket=updated,
            product=product,
            audit_event="product_released",
            requester=requester,
            audit_committed=self._transaction is not None,
        )

    def _commit_or_save(
        self,
        actor: UserAccount,
        expected: TicketRecord,
        proposed: TicketRecord,
        product: StoreProduct,
        event_type: str,
        notification: ReleaseNotificationIntent | None,
    ) -> TicketRecord:
        if self._transaction is None:
            return self._tickets.tickets.save_system_update_if_current(expected, proposed)
        committed = replace(proposed, updated_at=datetime.now(UTC))
        audit = WorkflowAuditIntent(
            event_type=event_type,
            actor_user_id=actor.user_id,
            metadata={
                "ticket_id": str(expected.ticket_id),
                "product_id": str(product.product_id),
                "qc_approved": "true",
            },
        )
        if not self._transaction.commit_qc_release(
            expected, committed, product, audit, notification
        ):
            raise AppError(
                409,
                "ticket_changed",
                "The ticket changed while the operation was running. Retry the operation.",
            )
        # The durable unit has committed. Cache refresh is an optimisation and
        # must not turn success into compensation against already-committed data.
        with suppress(Exception):
            self._tickets.tickets.accept_committed_system_update(committed)
        with suppress(Exception):
            self._store.repository.accept_committed(product)
        with suppress(Exception):
            self._audit_log.refresh_from_store()
        return committed

    def notify_best_effort(self, actor: UserAccount, outcome: QcReleaseOutcome) -> None:
        if outcome.requester is None:
            return
        try:
            self._notify_requester(outcome.requester, outcome.ticket, outcome.product)
        except Exception as exc:
            self._record_notification_failure(actor, outcome, exc)

    def _notify_requester(
        self, requester: UserAccount, ticket: TicketRecord, product: StoreProduct
    ) -> None:
        link_path = f"/store/products/{product.product_id}"
        self._notifications.notify(
            requester,
            "product_released",
            f"{ticket.reference} released",
            f"{product.metadata.title} is now available in the Intelligence Store.",
            link_path,
        )
        self._notifications.record_email(
            requester,
            f"Istari release: {ticket.reference}",
            f"Your requested product {product.reference} ({product.metadata.title}) has been "
            f"released. Open Istari and view it at {link_path}.",
        )

    def _record_notification_failure(
        self, actor: UserAccount, outcome: QcReleaseOutcome, exc: Exception
    ) -> None:
        try:
            self._audit_log.record(
                "product_release_notification_failed",
                str(actor.user_id),
                {
                    "ticket_id": str(outcome.ticket.ticket_id),
                    "product_id": str(outcome.product.product_id),
                    "error": type(exc).__name__,
                },
            )
        except Exception:
            return
