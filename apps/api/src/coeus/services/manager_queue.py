"""Team manager queues.

After JIOC approves a route, the ticket belongs to the owning team: the RFA
or CM manager assigns analysts and (from the manager-approval phase) reviews
their work. This service lists that team's active tickets; every action on
them lives in the assignment and approval services.
"""

from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.tickets import RoutingRoute, TicketRecord
from coeus.services.customer_outcomes import responsible_route
from coeus.services.manager_scope import require_route_manager
from coeus.services.prioritisation import priority_sort_key
from coeus.services.tickets import TicketServices

MANAGER_QUEUE_STATES = frozenset(
    {
        TicketState.ANALYST_ASSIGNMENT,
        TicketState.ANALYST_IN_PROGRESS,
        TicketState.MANAGER_APPROVAL,
        TicketState.MANAGER_REANALYSIS_REVIEW,
    }
)
MANAGER_READ_PERMISSIONS = frozenset({Permission.RFA_REVIEW, Permission.COLLECTION_REVIEW})


class ManagerQueueService:
    def __init__(self, tickets: TicketServices) -> None:
        self._tickets = tickets

    def queue(self, actor: UserAccount, route: RoutingRoute) -> tuple[TicketRecord, ...]:
        require_route_manager(actor, route)
        tickets = self._tickets.tickets.list_workflow_tickets(actor, MANAGER_READ_PERMISSIONS)
        queued = (
            ticket
            for ticket in tickets
            if ticket.state in MANAGER_QUEUE_STATES and responsible_route(ticket) == route
        )
        return tuple(sorted(queued, key=priority_sort_key))
