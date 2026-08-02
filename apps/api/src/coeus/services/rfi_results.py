"""Access-filtered projection of persisted RFI search results."""

from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.search_index import GroundedProductEvidence
from coeus.domain.tickets import TicketRecord
from coeus.services.rfi_result_projection import project_rfi_result_signal
from coeus.services.rfi_search_types import RfiSearchResults
from coeus.services.store_access import StoreDetailService
from coeus.services.tickets import TicketService


class RfiResultsService:
    def __init__(self, tickets: TicketService, store_details: StoreDetailService) -> None:
        self._tickets = tickets
        self._store_details = store_details

    def visible_offer_product_ids(
        self, actor: UserAccount, tickets: tuple[TicketRecord, ...]
    ) -> frozenset[UUID]:
        candidate_ids = frozenset(
            offer.product_id for ticket in tickets for offer in ticket.product_offers
        )
        return self._store_details.visible_product_ids(actor, candidate_ids)

    def ticket(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        review_permissions: frozenset[Permission],
        review_states: frozenset[TicketState],
    ) -> TicketRecord:
        try:
            return self._tickets.get_visible_ticket(actor, ticket_id)
        except AppError:
            ticket = self._tickets.get_workflow_ticket(actor, ticket_id, review_permissions)
            if ticket.state not in review_states:
                raise AppError(404, "ticket_not_found", "Ticket was not found.") from None
            return ticket

    def project(
        self,
        actor: UserAccount,
        ticket: TicketRecord,
        evidence: tuple[GroundedProductEvidence, ...] | None = None,
    ) -> RfiSearchResults:
        visible_ids = self.visible_offer_product_ids(actor, (ticket,))
        ticket = project_rfi_result_signal(
            ticket,
            visible_ids,
            preserve_full=ticket.requester_user_id == actor.user_id,
        )
        metric = ticket.search_metrics[-1] if ticket.search_metrics else None
        visible_evidence = tuple(
            item
            for item in (evidence if evidence is not None else ticket.search_evidence)
            if item.product_id in visible_ids
        )
        return RfiSearchResults(
            ticket=ticket,
            offers=ticket.product_offers,
            metrics=metric,
            evidence=visible_evidence,
            retrieval_mode=metric.retrieval_mode if metric else "metadata_only",
            degraded_reason=metric.degraded_reason if metric else None,
            outcome=metric.outcome if metric else "incomplete",
            assurance=metric.assurance if metric else "assisted",
        )
