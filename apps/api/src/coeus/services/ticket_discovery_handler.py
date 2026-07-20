"""Retry interrupted automatic discovery from durable ticket outbox events."""

from uuid import UUID

from coeus.application.ports.access import UserLookup
from coeus.core.logging import get_logger
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.jioc_routing import JiocRoutingMode, normalise_routing_mode
from coeus.domain.outbox import OutboxMessage
from coeus.domain.tickets import TicketRecord
from coeus.services.active_work_discovery import ActiveWorkDiscoveryService
from coeus.services.jioc_routing_agent import JiocRoutingAgentService
from coeus.services.rfi_search import RfiSearchService
from coeus.services.tickets import TicketServices

EVENT_TYPE = "ticket_shadow_changed"
logger = get_logger(__name__)


class TicketDiscoveryHandler:
    def __init__(
        self,
        tickets: TicketServices,
        access: UserLookup,
        rfi_search: RfiSearchService,
        active_work: ActiveWorkDiscoveryService,
        jioc_routing: JiocRoutingAgentService,
        automatic_discovery_enabled: bool = True,
        active_work_offers_enabled: bool = True,
        agent_routing_enabled: JiocRoutingMode | bool = JiocRoutingMode.DISABLED,
    ) -> None:
        self._tickets = tickets
        self._access = access
        self._rfi_search = rfi_search
        self._active_work = active_work
        self._jioc_routing = jioc_routing
        self._automatic_discovery_enabled = automatic_discovery_enabled
        self._active_work_offers_enabled = active_work_offers_enabled
        self._routing_mode = normalise_routing_mode(agent_routing_enabled)

    def __call__(self, message: OutboxMessage) -> None:
        if message.event_type != EVENT_TYPE:
            raise ValueError("Unexpected outbox event type for ticket discovery.")
        ticket = self._ticket(message)
        if ticket is None or ticket.state not in {
            TicketState.RFI_SEARCHING,
            TicketState.NEW_TASKING_CONSENT,
            TicketState.JIOC_ROUTING_PENDING,
        }:
            return
        if ticket.state == TicketState.JIOC_ROUTING_PENDING:
            self._route_with_agent(ticket.ticket_id)
            return
        if not self._automatic_discovery_enabled:
            return
        actor = self._access.get_user(ticket.requester_user_id)
        if actor is None or not actor.is_active:
            raise LookupError("Ticket requester is missing or inactive.")
        if not self._search_allows_active_work(actor, ticket):
            return
        latest = self._tickets.tickets.get_visible_ticket(actor, ticket.ticket_id)
        if not any(item.event_type == "active_work_search_completed" for item in latest.timeline):
            self._active_work.discover(actor, ticket.ticket_id)

    def _ticket(self, message: OutboxMessage) -> TicketRecord | None:
        return next(
            (
                item
                for item in self._tickets.tickets.assignment_snapshot()
                if item.ticket_id == message.aggregate_id
            ),
            None,
        )

    def _route_with_agent(self, ticket_id: UUID) -> None:
        if self._routing_mode is JiocRoutingMode.DISABLED:
            self._jioc_routing.defer_to_manager(ticket_id)
            return
        try:
            self._jioc_routing.route(
                ticket_id,
                apply=self._routing_mode is JiocRoutingMode.ACTIVE,
            )
        except Exception as exc:
            logger.exception(
                "jioc_routing_agent_deferred",
                extra={"ticket_id": str(ticket_id), "error": type(exc).__name__},
            )
            # A failure here is allowed to propagate so the durable outbox retries
            # rather than acknowledging a ticket that is still transient.
            self._jioc_routing.defer_to_manager(ticket_id, reason="routing_agent_failed")

    def _search_allows_active_work(self, actor: UserAccount, ticket: TicketRecord) -> bool:
        if ticket.state == TicketState.RFI_SEARCHING:
            result = self._rfi_search.run(actor, ticket.ticket_id)
            if result.ticket.state != TicketState.NEW_TASKING_CONSENT:
                return False
        return self._active_work_offers_enabled
