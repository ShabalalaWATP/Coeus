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
from coeus.services.capability_catalogue import CapabilityCatalogue, CapabilityCataloguePort
from coeus.services.orchestration_handoff import (
    append_collect_choice_handoff,
    append_handoff,
    collect_choice_handoff,
    manager_clarification_handoff,
)
from coeus.services.prioritisation import priority_sort_key
from coeus.services.routing_agents import (
    CmCapabilityAgent,
    CmReviewAgent,
    RfaCapabilityAgent,
    RfaReviewAgent,
)
from coeus.services.routing_records import (
    can_review_route,
    decision,
    decision_workflow_update,
    ensure_jioc_state,
    ensure_override,
    latest_recommendation,
    timeline,
)
from coeus.services.routing_review_updates import build_routing_review_update
from coeus.services.routing_stats import RoutingStats, routing_stats_from_tickets
from coeus.services.tickets import TicketServices

# JIOC owns route decisions; managers and JIOC share the advisory catalogue
# and routing statistics views.
ROUTING_READ_PERMISSIONS = frozenset(
    {Permission.JIOC_REVIEW, Permission.RFA_REVIEW, Permission.COLLECTION_REVIEW}
)


class RoutingService:
    """The JIOC decision service: capability advice in, human route decision out."""

    def __init__(
        self,
        tickets: TicketServices,
        audit_log: AuditLog,
        catalogue: CapabilityCataloguePort,
        rfa_agent: RfaReviewAgent,
        cm_agent: CmReviewAgent,
    ) -> None:
        self._tickets = tickets
        self._audit_log = audit_log
        self._catalogue = catalogue
        self._rfa_agent = rfa_agent
        self._cm_agent = cm_agent

    def jioc_queue(self, actor: UserAccount) -> tuple[TicketRecord, ...]:
        self._require(actor, Permission.JIOC_REVIEW)
        tickets = self._tickets.tickets.list_workflow_tickets(actor, ROUTING_READ_PERMISSIONS)
        queued = (
            ticket
            for ticket in tickets
            if ticket.state in {TicketState.JIOC_REVIEW, TicketState.COLLECT_CHOICE}
        )
        return tuple(sorted(queued, key=priority_sort_key))

    def capability_catalogue(self, actor: UserAccount) -> tuple[CapabilityTeam, ...]:
        if not ROUTING_READ_PERMISSIONS.intersection(actor.permissions):
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
        self._require(actor, Permission.JIOC_REVIEW)
        ticket = self._tickets.tickets.get_workflow_ticket(
            actor, ticket_id, ROUTING_READ_PERMISSIONS
        )
        ensure_jioc_state(ticket)
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
        self._require(actor, Permission.JIOC_REVIEW)
        ticket = self.details(actor, ticket_id)
        ensure_jioc_state(ticket)
        recommendation = latest_recommendation(ticket)
        if recommendation.recommended_route != route:
            ensure_override(override_reason)
        collection = route == RoutingRoute.CM
        target = TicketState.COLLECT_CHOICE if collection else TicketState.ANALYST_ASSIGNMENT
        self._ensure_transition(ticket.state, target)
        reason = (
            "Collection required; awaiting the customer's collect choice."
            if collection
            else "Collection not required; approved for RFA analyst assignment."
        )
        manager_decision = decision(
            ticket.ticket_id,
            actor.user_id,
            route,
            ManagerRoutingDecisionStatus.APPROVED,
            reason,
            override_reason,
        )
        event_type = "manager_override" if override_reason else "route_approved"
        return self._save_decision(
            ticket, manager_decision, target, event_type, notify_collect_choice=collection
        )

    def reject(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        route: RoutingRoute,
        reason: str,
    ) -> TicketRecord:
        self._require(actor, Permission.JIOC_REVIEW)
        ticket = self.details(actor, ticket_id)
        ensure_jioc_state(ticket)
        self._ensure_transition(ticket.state, TicketState.INFO_REQUIRED)
        manager_decision = decision(
            ticket.ticket_id,
            actor.user_id,
            route,
            ManagerRoutingDecisionStatus.REJECTED,
            reason,
            None,
        )
        return self._save_decision(
            ticket, manager_decision, TicketState.INFO_REQUIRED, "route_rejected"
        )

    def request_clarification(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        route: RoutingRoute,
        reason: str,
        questions: tuple[str, ...],
    ) -> TicketRecord:
        self._require(actor, Permission.JIOC_REVIEW)
        ticket = self.details(actor, ticket_id)
        ensure_jioc_state(ticket)
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
            self._decision_update(ticket, manager_decision, TicketState.INFO_REQUIRED),
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

    def _decision_update(
        self,
        ticket: TicketRecord,
        manager_decision: ManagerRoutingDecision,
        state: TicketState,
    ) -> TicketRecord:
        return replace(
            ticket,
            state=state,
            manager_decisions=(*ticket.manager_decisions, manager_decision),
            workflow_plan_updates=(
                *ticket.workflow_plan_updates,
                decision_workflow_update(ticket.ticket_id, manager_decision, state),
            ),
            timeline=(
                *ticket.timeline,
                timeline(
                    ticket.ticket_id,
                    manager_decision.actor_user_id,
                    f"route_{manager_decision.status.value}",
                    manager_decision.reason,
                ),
            ),
        )

    def _save_decision(
        self,
        ticket: TicketRecord,
        manager_decision: ManagerRoutingDecision,
        state: TicketState,
        event_type: str,
        notify_collect_choice: bool = False,
    ) -> TicketRecord:
        proposed = self._decision_update(ticket, manager_decision, state)
        if notify_collect_choice:
            proposed = append_collect_choice_handoff(
                proposed,
                collect_choice_handoff(ticket.ticket_id, manager_decision.actor_user_id),
            )
        return self._save_with_audit(
            ticket,
            proposed,
            event_type,
            manager_decision.actor_user_id,
            {"ticket_id": str(ticket.ticket_id), "route": manager_decision.route.value},
        )

    def _save_with_audit(
        self,
        original: TicketRecord,
        proposed: TicketRecord,
        event_type: str,
        actor_user_id: UUID,
        metadata: dict[str, str],
    ) -> TicketRecord:
        return self._tickets.mutations.save_audited_if_current(
            original, proposed, event_type, actor_user_id, metadata
        )

    @staticmethod
    def _require(actor: UserAccount, permission: Permission) -> None:
        if permission not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")

    @staticmethod
    def _ensure_transition(current: TicketState, target: TicketState) -> None:
        if current != target and not can_transition(current, target):
            raise AppError(409, "invalid_ticket_state", "Ticket cannot move to that state.")


def build_routing_service(ticket_services: TicketServices, audit_log: AuditLog) -> RoutingService:
    catalogue = CapabilityCatalogue()
    return RoutingService(
        ticket_services,
        audit_log,
        catalogue,
        RfaCapabilityAgent(catalogue),
        CmCapabilityAgent(catalogue),
    )
