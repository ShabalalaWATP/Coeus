from dataclasses import dataclass

from coeus.domain.enums import TicketState
from coeus.domain.tickets import ManagerRoutingDecisionStatus, RoutingRoute, TicketRecord
from coeus.services.routing_records import count_state, rate


@dataclass(frozen=True)
class RoutingStats:
    route_assessment_count: int
    rfa_review_count: int
    cm_review_count: int
    clarification_count: int
    analyst_assignment_count: int
    rfa_acceptance_rate: float
    cm_fallback_rate: float


def routing_stats_from_tickets(tickets: tuple[TicketRecord, ...]) -> RoutingStats:
    decisions = [decision for ticket in tickets for decision in ticket.manager_decisions]
    recommendations = [rec for ticket in tickets for rec in ticket.route_recommendations]
    approved = [item for item in decisions if item.status == ManagerRoutingDecisionStatus.APPROVED]
    rfa_approved = [item for item in approved if item.route == RoutingRoute.RFA]
    cm_fallbacks = [item for item in recommendations if item.recommended_route == RoutingRoute.CM]
    return RoutingStats(
        route_assessment_count=count_state(tickets, TicketState.ROUTE_ASSESSMENT),
        rfa_review_count=count_state(tickets, TicketState.RFA_MANAGER_REVIEW),
        cm_review_count=count_state(tickets, TicketState.CM_MANAGER_REVIEW),
        clarification_count=count_state(tickets, TicketState.INFO_REQUIRED),
        analyst_assignment_count=count_state(tickets, TicketState.ANALYST_ASSIGNMENT),
        rfa_acceptance_rate=rate(len(rfa_approved), len(approved)),
        cm_fallback_rate=rate(len(cm_fallbacks), len(recommendations)),
    )
