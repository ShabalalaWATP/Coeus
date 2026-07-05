from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.state_machine import can_transition
from coeus.domain.tickets import (
    ClarificationRequest,
    ManagerRoutingDecision,
    ManagerRoutingDecisionStatus,
    RoutingRoute,
    TicketRecord,
)
from coeus.services.audit import AuditLog
from coeus.services.routing_agents import CmCapabilityAgent, RfaCapabilityAgent
from coeus.services.routing_records import (
    agent_run,
    can_review_route,
    count_state,
    decision,
    decision_project_update,
    fallback_state,
    filled,
    latest_cm_review,
    latest_recommendation,
    project_update,
    rate,
    recommend_route,
    state_for_recommendation,
    timeline,
)
from coeus.services.tickets import TicketServices

ROUTING_READ_PERMISSIONS = frozenset({Permission.RFA_REVIEW, Permission.COLLECTION_REVIEW})


@dataclass(frozen=True)
class RoutingStats:
    route_assessment_count: int
    rfa_review_count: int
    cm_review_count: int
    clarification_count: int
    analyst_assignment_count: int
    rfa_acceptance_rate: float
    cm_fallback_rate: float


class RoutingService:
    def __init__(
        self,
        tickets: TicketServices,
        audit_log: AuditLog,
        rfa_agent: RfaCapabilityAgent | None = None,
        cm_agent: CmCapabilityAgent | None = None,
    ) -> None:
        self._tickets = tickets
        self._audit_log = audit_log
        self._rfa_agent = rfa_agent or RfaCapabilityAgent()
        self._cm_agent = cm_agent or CmCapabilityAgent()

    def rfa_queue(self, actor: UserAccount) -> tuple[TicketRecord, ...]:
        self._require(actor, Permission.RFA_REVIEW)
        return self._queue_for(
            actor,
            {TicketState.ROUTE_ASSESSMENT, TicketState.RFA_MANAGER_REVIEW},
        )

    def cm_queue(self, actor: UserAccount) -> tuple[TicketRecord, ...]:
        self._require(actor, Permission.COLLECTION_REVIEW)
        return self._queue_for(actor, {TicketState.CM_MANAGER_REVIEW})

    def details(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        ticket = self._tickets.tickets.get_workflow_ticket(
            actor, ticket_id, ROUTING_READ_PERMISSIONS
        )
        if not can_review_route(actor, ticket):
            raise AppError(404, "ticket_not_found", "Ticket was not found.")
        return ticket

    def run_reviews(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        if (
            Permission.RFA_REVIEW not in actor.permissions
            and Permission.COLLECTION_REVIEW not in actor.permissions
        ):
            raise AppError(403, "forbidden", "Permission denied.")
        ticket = self._tickets.tickets.get_workflow_ticket(
            actor, ticket_id, ROUTING_READ_PERMISSIONS
        )
        if ticket.state != TicketState.ROUTE_ASSESSMENT:
            raise AppError(409, "invalid_ticket_state", "Ticket is not awaiting route assessment.")
        rfa_review = self._rfa_agent.review(ticket)
        cm_review = self._cm_agent.review(ticket)
        recommendation = recommend_route(ticket.ticket_id, rfa_review, cm_review)
        target_state = state_for_recommendation(recommendation)
        self._ensure_transition(ticket.state, target_state)
        updated = self._tickets.tickets.save_system_update(
            replace(
                ticket,
                state=target_state,
                rfa_reviews=(*ticket.rfa_reviews, rfa_review),
                cm_reviews=(*ticket.cm_reviews, cm_review),
                route_recommendations=(*ticket.route_recommendations, recommendation),
                agent_runs=(
                    *ticket.agent_runs,
                    agent_run(ticket.ticket_id, "rfa-capability", rfa_review.reasoning_summary),
                    agent_run(ticket.ticket_id, "cm-capability", cm_review.reasoning_summary),
                ),
                project_plan_updates=(
                    *ticket.project_plan_updates,
                    project_update(ticket.ticket_id, target_state, recommendation),
                ),
                timeline=(
                    *ticket.timeline,
                    timeline(
                        ticket.ticket_id,
                        actor.user_id,
                        "route_reviews_completed",
                        recommendation.reasoning_summary,
                    ),
                ),
            )
        )
        self._audit_log.record(
            "route_reviews_completed",
            str(actor.user_id),
            {
                "ticket_id": str(ticket.ticket_id),
                "recommended_route": recommendation.recommended_route.value,
            },
        )
        return updated

    def approve(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        route: RoutingRoute,
        override_reason: str | None,
    ) -> TicketRecord:
        self._require_route_permission(actor, route)
        ticket = self.details(actor, ticket_id)
        recommendation = latest_recommendation(ticket)
        if recommendation.recommended_route == route:
            self._ensure_manager_state(ticket, route)
        else:
            self._ensure_override(ticket, override_reason)
        self._ensure_transition(ticket.state, TicketState.ANALYST_ASSIGNMENT)
        manager_decision = decision(
            ticket.ticket_id,
            actor.user_id,
            route,
            ManagerRoutingDecisionStatus.APPROVED,
            "Approved for analyst assignment.",
            override_reason,
        )
        event_type = "manager_override" if override_reason else "route_approved"
        updated = self._save_decision(ticket, manager_decision, TicketState.ANALYST_ASSIGNMENT)
        self._audit_log.record(
            event_type,
            str(actor.user_id),
            {"ticket_id": str(ticket.ticket_id), "route": route.value},
        )
        return updated

    def reject(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        route: RoutingRoute,
        reason: str,
    ) -> TicketRecord:
        self._require_route_permission(actor, route)
        ticket = self.details(actor, ticket_id)
        self._ensure_manager_state(ticket, route)
        target_state = fallback_state(route, latest_cm_review(ticket))
        self._ensure_transition(ticket.state, target_state)
        manager_decision = decision(
            ticket.ticket_id,
            actor.user_id,
            route,
            ManagerRoutingDecisionStatus.REJECTED,
            reason,
            None,
        )
        updated = self._save_decision(ticket, manager_decision, target_state)
        self._audit_log.record(
            "route_rejected",
            str(actor.user_id),
            {"ticket_id": str(ticket.ticket_id), "route": route.value},
        )
        return updated

    def request_clarification(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        route: RoutingRoute,
        reason: str,
        questions: tuple[str, ...],
    ) -> TicketRecord:
        self._require_route_permission(actor, route)
        ticket = self.details(actor, ticket_id)
        self._ensure_manager_state(ticket, route)
        self._ensure_transition(ticket.state, TicketState.INFO_REQUIRED)
        clarification = ClarificationRequest(
            clarification_id=uuid4(),
            ticket_id=ticket.ticket_id,
            route=route,
            reason=reason,
            questions=questions,
            requested_by_user_id=actor.user_id,
            created_at=datetime.now(UTC),
        )
        manager_decision = decision(
            ticket.ticket_id,
            actor.user_id,
            route,
            ManagerRoutingDecisionStatus.CLARIFICATION_REQUESTED,
            reason,
            None,
        )
        updated = self._tickets.tickets.save_system_update(
            replace(
                ticket,
                state=TicketState.INFO_REQUIRED,
                clarification_requests=(*ticket.clarification_requests, clarification),
                manager_decisions=(*ticket.manager_decisions, manager_decision),
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "clarification_requested", reason),
                ),
            )
        )
        self._audit_log.record(
            "route_clarification_requested",
            str(actor.user_id),
            {"ticket_id": str(ticket.ticket_id), "route": route.value},
        )
        return updated

    def stats(self, actor: UserAccount) -> RoutingStats:
        if (
            Permission.ANALYTICS_VIEW_TEAM not in actor.permissions
            and Permission.ANALYTICS_VIEW_GLOBAL not in actor.permissions
        ):
            raise AppError(403, "forbidden", "Permission denied.")
        tickets = self._tickets.tickets.list_workflow_tickets(actor, ROUTING_READ_PERMISSIONS)
        decisions = [decision for ticket in tickets for decision in ticket.manager_decisions]
        recommendations = [rec for ticket in tickets for rec in ticket.route_recommendations]
        approved = [
            item for item in decisions if item.status == ManagerRoutingDecisionStatus.APPROVED
        ]
        rfa_approved = [item for item in approved if item.route == RoutingRoute.RFA]
        cm_fallbacks = [
            item for item in recommendations if item.recommended_route == RoutingRoute.CM
        ]
        return RoutingStats(
            route_assessment_count=count_state(tickets, TicketState.ROUTE_ASSESSMENT),
            rfa_review_count=count_state(tickets, TicketState.RFA_MANAGER_REVIEW),
            cm_review_count=count_state(tickets, TicketState.CM_MANAGER_REVIEW),
            clarification_count=count_state(tickets, TicketState.INFO_REQUIRED),
            analyst_assignment_count=count_state(tickets, TicketState.ANALYST_ASSIGNMENT),
            rfa_acceptance_rate=rate(len(rfa_approved), len(approved)),
            cm_fallback_rate=rate(len(cm_fallbacks), len(recommendations)),
        )

    def _queue_for(self, actor: UserAccount, states: set[TicketState]) -> tuple[TicketRecord, ...]:
        tickets = self._tickets.tickets.list_workflow_tickets(actor, ROUTING_READ_PERMISSIONS)
        return tuple(ticket for ticket in tickets if ticket.state in states)

    def _save_decision(
        self,
        ticket: TicketRecord,
        decision: ManagerRoutingDecision,
        state: TicketState,
    ) -> TicketRecord:
        return self._tickets.tickets.save_system_update(
            replace(
                ticket,
                state=state,
                manager_decisions=(*ticket.manager_decisions, decision),
                project_plan_updates=(
                    *ticket.project_plan_updates,
                    decision_project_update(ticket.ticket_id, decision, state),
                ),
                timeline=(
                    *ticket.timeline,
                    timeline(
                        ticket.ticket_id,
                        decision.actor_user_id,
                        f"route_{decision.status.value}",
                        decision.reason,
                    ),
                ),
            )
        )

    @staticmethod
    def _require(actor: UserAccount, permission: Permission) -> None:
        if permission not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")

    def _require_route_permission(self, actor: UserAccount, route: RoutingRoute) -> None:
        permission = (
            Permission.RFA_REVIEW if route == RoutingRoute.RFA else Permission.COLLECTION_REVIEW
        )
        self._require(actor, permission)

    @staticmethod
    def _ensure_transition(current: TicketState, target: TicketState) -> None:
        if not can_transition(current, target):
            raise AppError(
                409,
                "invalid_ticket_state",
                "Ticket cannot move to the requested state.",
            )

    @staticmethod
    def _ensure_manager_state(ticket: TicketRecord, route: RoutingRoute) -> None:
        allowed = {
            RoutingRoute.RFA: TicketState.RFA_MANAGER_REVIEW,
            RoutingRoute.CM: TicketState.CM_MANAGER_REVIEW,
        }
        if ticket.state != allowed[route]:
            raise AppError(409, "invalid_ticket_state", "Ticket is not in that manager queue.")

    @staticmethod
    def _ensure_override(ticket: TicketRecord, override_reason: str | None) -> None:
        if ticket.state not in {TicketState.RFA_MANAGER_REVIEW, TicketState.CM_MANAGER_REVIEW}:
            raise AppError(409, "invalid_ticket_state", "Ticket is not in manager review.")
        if not filled(override_reason):
            raise AppError(422, "override_reason_required", "Override reason is required.")


def build_routing_service(ticket_services: TicketServices, audit_log: AuditLog) -> RoutingService:
    return RoutingService(ticket_services, audit_log)
