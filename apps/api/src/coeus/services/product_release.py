from dataclasses import replace
from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.access import ProductStatus
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.state_machine import can_transition
from coeus.domain.store import StoreProduct
from coeus.domain.tickets import RoutingRoute, TicketRecord
from coeus.repositories.access import SeedAccessRepository
from coeus.services.analyst_records import approved_route
from coeus.services.audit import AuditLog
from coeus.services.notifications import NotificationService
from coeus.services.qc_records import dissemination, feedback_request
from coeus.services.store import StoreServices
from coeus.services.ticket_records import timeline
from coeus.services.tickets import TicketServices

RELEASE_READ_PERMISSIONS = frozenset({Permission.RFA_REVIEW, Permission.COLLECTION_REVIEW})
ROUTE_PERMISSIONS: dict[RoutingRoute, Permission] = {
    RoutingRoute.RFA: Permission.RFA_REVIEW,
    RoutingRoute.CM: Permission.COLLECTION_REVIEW,
}


class ProductReleaseService:
    """Final release of QC-approved products by the owning route manager."""

    def __init__(
        self,
        tickets: TicketServices,
        store: StoreServices,
        access: SeedAccessRepository,
        notifications: NotificationService,
        audit_log: AuditLog,
    ) -> None:
        self._tickets = tickets
        self._store = store
        self._access = access
        self._notifications = notifications
        self._audit_log = audit_log

    def queue(self, actor: UserAccount, route: RoutingRoute) -> tuple[TicketRecord, ...]:
        self._require(actor, ROUTE_PERMISSIONS[route])
        return tuple(
            ticket
            for ticket in self._tickets.tickets.list_workflow_tickets(
                actor, RELEASE_READ_PERMISSIONS
            )
            if ticket.state == TicketState.MANAGER_RELEASE and approved_route(ticket) == route
        )

    def release(self, actor: UserAccount, ticket_id: UUID, route: RoutingRoute) -> TicketRecord:
        self._require(actor, ROUTE_PERMISSIONS[route])
        self._require(actor, Permission.PRODUCT_DISSEMINATE)
        ticket = self._tickets.tickets.get_workflow_ticket(
            actor, ticket_id, RELEASE_READ_PERMISSIONS
        )
        if ticket.state != TicketState.MANAGER_RELEASE or approved_route(ticket) != route:
            raise AppError(409, "invalid_ticket_state", "Ticket is not awaiting final release.")
        if not can_transition(ticket.state, TicketState.DISSEMINATION_READY):
            raise AppError(409, "invalid_ticket_state", "Ticket cannot move to that state.")
        product = self._published_product(ticket)
        requester = self._access.get_user(ticket.requester_user_id)
        if requester is None or not requester.is_active:
            raise AppError(409, "requester_not_active", "Requester must be active.")
        self._store.details.get_visible_product(requester, product.product_id)
        dissemination_record = dissemination(
            ticket.ticket_id, product.product_id, requester.user_id
        )
        feedback = feedback_request(ticket.ticket_id, product.product_id, requester.user_id)
        self._notify_requester(requester, ticket, product)
        updated = self._tickets.tickets.save_system_update(
            replace(
                ticket,
                state=TicketState.DISSEMINATION_READY,
                disseminations=(*ticket.disseminations, dissemination_record),
                feedback_requests=(*ticket.feedback_requests, feedback),
                timeline=(
                    *ticket.timeline,
                    timeline(
                        ticket.ticket_id, actor.user_id, "manager_released", product.reference
                    ),
                    timeline(
                        ticket.ticket_id, actor.user_id, "product_disseminated", product.reference
                    ),
                    timeline(
                        ticket.ticket_id, actor.user_id, "customer_notified", requester.username
                    ),
                ),
            )
        )
        self._audit_log.record(
            "product_released",
            str(actor.user_id),
            {"ticket_id": str(ticket_id), "product_id": str(product.product_id)},
        )
        return updated

    def _published_product(self, ticket: TicketRecord) -> StoreProduct:
        if not ticket.product_index_records:
            raise AppError(409, "product_not_ingested", "No QC-approved product to release.")
        product_id = ticket.product_index_records[-1].product_id
        product = self._store.repository.get_product(product_id)
        if product is None:
            raise AppError(409, "product_not_ingested", "No QC-approved product to release.")
        published = replace(
            product,
            metadata=replace(product.metadata, status=ProductStatus.PUBLISHED),
        )
        self._store.repository.save_product(published)
        return published

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

    @staticmethod
    def _require(actor: UserAccount, permission: Permission) -> None:
        if permission not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
