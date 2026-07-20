"""Orchestrate customer consent into the autonomous JIOC routing step."""

from uuid import UUID

from coeus.core.logging import get_logger
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.tickets import TicketRecord
from coeus.services.jioc_routing_agent import JiocRoutingAgentService
from coeus.services.ticket_lifecycle import TicketLifecycleService

logger = get_logger(__name__)


class TaskingConsentService:
    def __init__(
        self,
        lifecycle: TicketLifecycleService,
        routing_agent: JiocRoutingAgentService,
        agent_routing_enabled: bool = True,
    ) -> None:
        self._lifecycle = lifecycle
        self._routing_agent = routing_agent
        self._agent_routing_enabled = agent_routing_enabled

    def decide(
        self, actor: UserAccount, ticket_id: UUID, task_as_new_request: bool
    ) -> TicketRecord:
        ticket = self._lifecycle.no_match_consent(actor, ticket_id, task_as_new_request)
        if ticket.state != TicketState.JIOC_ROUTING_PENDING or not self._agent_routing_enabled:
            return ticket
        try:
            return self._routing_agent.route(ticket.ticket_id)
        except Exception as exc:
            logger.exception(
                "jioc_routing_agent_deferred",
                extra={"ticket_id": str(ticket.ticket_id), "error": type(exc).__name__},
            )
            return ticket
