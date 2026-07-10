from dataclasses import replace
from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.capabilities import CapabilityTeam
from coeus.domain.enums import TicketState
from coeus.domain.state_machine import can_transition
from coeus.domain.tickets import (
    ManagerRoutingDecision,
    ManagerRoutingDecisionStatus,
    RoutingRoute,
    TicketRecord,
)
from coeus.services.audit import AuditLog
from coeus.services.capability_catalogue import CapabilityCatalogue
from coeus.services.orchestration_handoff import (
    append_handoff,
    manager_clarification_handoff,
)
from coeus.services.routing_agents import CmCapabilityAgent, RfaCapabilityAgent
from coeus.services.routing_records import (
    can_review_route,
    current_queue_permission,
    decision,
    decision_workflow_update,
    ensure_manager_state,
    ensure_override,
    fallback_state,
    latest_cm_review,
    latest_recommendation,
    timeline,
)
from coeus.services.routing_review_updates import build_routing_review_update
from coeus.services.routing_stats import RoutingStats, routing_stats_from_tickets
from coeus.services.tickets import TicketServices

ROUTING_READ_PERMISSIONS = frozenset({Permission.RFA_REVIEW, Permission.COLLECTION_REVIEW})


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
        self._catalogue = CapabilityCatalogue()
        self._rfa_agent = rfa_agent or RfaCapabilityAgent(self._catalogue)
        self._cm_agent = cm_agent or CmCapabilityAgent(self._catalogue)

    def rfa_queue(self, actor: UserAccount) -> tuple[TicketRecord, ...]:
        self._require(actor, Permission.RFA_REVIEW)
        return self._queue_for(
            actor,
            {TicketState.ROUTE_ASSESSMENT, TicketState.RFA_MANAGER_REVIEW},
        )

    def cm_queue(self, actor: UserAccount) -> tuple[TicketRecord, ...]:
        self._require(actor, Permission.COLLECTION_REVIEW)
        return self._queue_for(actor, {TicketState.CM_MANAGER_REVIEW})

    def capability_catalogue(self, actor: UserAccount) -> tuple[CapabilityTeam, ...]:
        if (
            Permission.RFA_REVIEW not in actor.permissions
            and Permission.COLLECTION_REVIEW not in actor.permissions
        ):
            raise AppError(403, "forbidden", "Permission denied.")
        return (*self._catalogue.rfa_teams(), *self._catalogue.cm_teams())

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
        review_update = build_routing_review_update(ticket, actor.user_id, rfa_review, cm_review)
        self._ensure_transition(ticket.state, review_update.target_state)
        return self._save_with_audit(
            ticket,
            review_update.proposed,
            "route_reviews_completed",
            actor.user_id,
            review_update.metadata,
        )

    def approve(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        route: RoutingRoute,
        override_reason: str | None,
    ) -> TicketRecord:
        ticket = self.details(actor, ticket_id)
        recommendation = latest_recommendation(ticket)
        # The approving manager must own the queue the ticket currently sits
        # in; an override changes the route, never which queue can decide.
        self._require_current_queue_permission(actor, ticket)
        if recommendation.recommended_route == route:
            ensure_manager_state(ticket, route)
        else:
            ensure_override(override_reason)
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
        return self._save_decision(
            ticket, manager_decision, TicketState.ANALYST_ASSIGNMENT, event_type
        )

    def reject(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        route: RoutingRoute,
        reason: str,
    ) -> TicketRecord:
        self._require_route_permission(actor, route)
        ticket = self.details(actor, ticket_id)
        ensure_manager_state(ticket, route)
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
        return self._save_decision(ticket, manager_decision, target_state, "route_rejected")

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
        ensure_manager_state(ticket, route)
        self._ensure_transition(ticket.state, TicketState.INFO_REQUIRED)
        handoff = manager_clarification_handoff(
            ticket.ticket_id, actor.user_id, route, reason, questions
        )
        manager_decision = decision(
            ticket.ticket_id,
            actor.user_id,
            route,
            ManagerRoutingDecisionStatus.CLARIFICATION_REQUESTED,
            reason,
            None,
        )
        proposed = append_handoff(
            replace(
                ticket,
                state=TicketState.INFO_REQUIRED,
                manager_decisions=(*ticket.manager_decisions, manager_decision),
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "clarification_requested", reason),
                ),
            ),
            handoff,
        )
        return self._save_with_audit(
            ticket,
            proposed,
            "route_clarification_requested",
            actor.user_id,
            {"ticket_id": str(ticket.ticket_id), "route": route.value},
        )

    def stats(self, actor: UserAccount) -> RoutingStats:
        if (
            Permission.ANALYTICS_VIEW_TEAM not in actor.permissions
            and Permission.ANALYTICS_VIEW_GLOBAL not in actor.permissions
        ):
            raise AppError(403, "forbidden", "Permission denied.")
        tickets = self._tickets.tickets.list_workflow_tickets(actor, ROUTING_READ_PERMISSIONS)
        return routing_stats_from_tickets(tickets)

    def _queue_for(self, actor: UserAccount, states: set[TicketState]) -> tuple[TicketRecord, ...]:
        tickets = self._tickets.tickets.list_workflow_tickets(actor, ROUTING_READ_PERMISSIONS)
        return tuple(ticket for ticket in tickets if ticket.state in states)

    def _save_decision(
        self,
        ticket: TicketRecord,
        decision: ManagerRoutingDecision,
        state: TicketState,
        event_type: str,
    ) -> TicketRecord:
        proposed = replace(
            ticket,
            state=state,
            manager_decisions=(*ticket.manager_decisions, decision),
            workflow_plan_updates=(
                *ticket.workflow_plan_updates,
                decision_workflow_update(ticket.ticket_id, decision, state),
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
        return self._save_with_audit(
            ticket,
            proposed,
            event_type,
            decision.actor_user_id,
            {"ticket_id": str(ticket.ticket_id), "route": decision.route.value},
        )

    def _save_with_audit(
        self,
        original: TicketRecord,
        proposed: TicketRecord,
        event_type: str,
        actor_user_id: UUID,
        metadata: dict[str, str],
    ) -> TicketRecord:
        updated = self._tickets.tickets.save_system_update(proposed)
        try:
            self._audit_log.record(event_type, str(actor_user_id), metadata)
        except Exception:
            self._tickets.tickets.save_system_update(original)
            raise
        return updated

    @staticmethod
    def _require(actor: UserAccount, permission: Permission) -> None:
        if permission not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")

    def _require_route_permission(self, actor: UserAccount, route: RoutingRoute) -> None:
        permission = (
            Permission.RFA_REVIEW if route == RoutingRoute.RFA else Permission.COLLECTION_REVIEW
        )
        self._require(actor, permission)

    def _require_current_queue_permission(self, actor: UserAccount, ticket: TicketRecord) -> None:
        self._require(actor, current_queue_permission(ticket))

    @staticmethod
    def _ensure_transition(current: TicketState, target: TicketState) -> None:
        if not can_transition(current, target):
            raise AppError(409, "invalid_ticket_state", "Ticket cannot move to that state.")


def build_routing_service(ticket_services: TicketServices, audit_log: AuditLog) -> RoutingService:
    return RoutingService(ticket_services, audit_log)
