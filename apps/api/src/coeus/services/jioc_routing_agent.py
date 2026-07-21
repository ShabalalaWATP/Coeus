"""Autonomous, policy-constrained JIOC routing with a human exception queue."""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.domain.enums import TicketState
from coeus.domain.jioc_routing import (
    ROUTING_POLICY_VERSION,
    JiocRoutingDecision,
)
from coeus.domain.tickets import (
    CmCapabilityReview,
    RfaCapabilityReview,
    RouteRecommendation,
    TicketRecord,
)
from coeus.services.capability_catalogue import CapabilityCatalogue
from coeus.services.jioc_routing_context import (
    MissingOperationalContext,
    RoutingOperationalContextPort,
    build_routing_context,
)
from coeus.services.jioc_routing_policy import (
    candidate_team_ids as _candidate_team_ids,
)
from coeus.services.jioc_routing_policy import (
    decide as _decide,
)
from coeus.services.jioc_routing_policy import (
    evidence_outcome as _evidence_outcome,
)
from coeus.services.jioc_routing_policy import (
    target_state as _target,
)
from coeus.services.orchestration_handoff import (
    append_collect_choice_handoff,
    collect_choice_handoff,
)
from coeus.services.routing_agents import (
    CmCapabilityAgent,
    CmReviewAgent,
    RfaCapabilityAgent,
    RfaReviewAgent,
)
from coeus.services.routing_critic_intent import routing_critique_intent
from coeus.services.routing_records import (
    agent_run,
    latest_recommendation,
    provenance_hash,
    recommend_route,
    review_agent_runs,
    timeline,
    workflow_update,
)
from coeus.services.routing_review_updates import build_routing_review_update
from coeus.services.tickets import TicketServices

JIOC_AGENT_PRINCIPAL = UUID("00000000-0000-0000-0000-000000000002")


class JiocRoutingAgentService:
    """Apply routine route decisions and abstain to JIOC manager review."""

    def __init__(
        self,
        tickets: TicketServices,
        *,
        rfa_agent: RfaReviewAgent | None = None,
        cm_agent: CmReviewAgent | None = None,
        operational_context: RoutingOperationalContextPort | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._tickets = tickets
        catalogue = CapabilityCatalogue()
        self._rfa_agent = rfa_agent or RfaCapabilityAgent(catalogue)
        self._cm_agent = cm_agent or CmCapabilityAgent(catalogue)
        self._operational_context = operational_context or MissingOperationalContext()
        self._clock = clock or (lambda: datetime.now(UTC))

    def route(self, ticket_id: UUID, *, apply: bool = True) -> TicketRecord:
        ticket = self._ticket(ticket_id)
        if ticket.state != TicketState.JIOC_ROUTING_PENDING:
            return ticket

        rfa_review = self._rfa_agent.review(ticket)
        cm_review = self._cm_agent.review(ticket)
        candidate_ids = _candidate_team_ids(rfa_review, cm_review)
        context = build_routing_context(
            ticket,
            self._operational_context.snapshot(ticket, candidate_ids),
            self._clock(),
        )
        disposition, route, confidence, codes, questions = _decide(
            ticket, context, rfa_review, cm_review
        )
        evidence_outcome = _evidence_outcome(rfa_review, cm_review, disposition)
        shadow = not apply
        disposition = disposition if apply else "shadow_recommendation"
        automatic = disposition == "auto_applied"
        rfa_review = replace(rfa_review, manager_review_required=not automatic)
        cm_review = replace(cm_review, manager_review_required=not automatic)
        recommendation = recommend_route(ticket.ticket_id, rfa_review, cm_review)
        if recommendation.recommended_route != route:
            recommendation = replace(
                recommendation,
                recommended_route=route,
                reasoning_summary=_reason(codes),
            )
        if shadow:
            proposed = _shadow_review(ticket, rfa_review, cm_review, recommendation)
        else:
            review = build_routing_review_update(
                ticket, JIOC_AGENT_PRINCIPAL, rfa_review, cm_review
            )
            current_recommendation = latest_recommendation(review.proposed)
            if current_recommendation.recommended_route == recommendation.recommended_route:
                recommendation = current_recommendation
            else:
                handoff_runs = review.proposed.agent_runs[len(ticket.agent_runs) + 3 :]
                review = replace(
                    review,
                    proposed=replace(
                        review.proposed,
                        route_recommendations=(
                            *review.proposed.route_recommendations[:-1],
                            recommendation,
                        ),
                        agent_runs=(
                            *ticket.agent_runs,
                            *review_agent_runs(ticket, rfa_review, cm_review, recommendation),
                            *handoff_runs,
                        ),
                    ),
                )
            proposed = review.proposed
        decision = JiocRoutingDecision(
            decision_id=uuid4(),
            ticket_id=ticket.ticket_id,
            context_id=context.context_id,
            recommended_route=route.value,
            disposition=disposition,
            confidence=confidence,
            rationale_codes=codes,
            required_clarifications=questions,
            policy_version=ROUTING_POLICY_VERSION,
            created_at=self._clock(),
            evidence_outcome=evidence_outcome,
        )
        target = _target(disposition, route)
        updated_timeline = proposed.timeline
        if not shadow:
            updated_timeline = (
                *proposed.timeline,
                timeline(
                    ticket.ticket_id,
                    JIOC_AGENT_PRINCIPAL,
                    _event_type(disposition),
                    _customer_safe_timeline(target),
                ),
            )
        proposed = replace(
            proposed,
            state=target,
            jioc_routing_contexts=(*ticket.jioc_routing_contexts, context),
            jioc_routing_decisions=(*ticket.jioc_routing_decisions, decision),
            workflow_plan_updates=(
                *proposed.workflow_plan_updates[:-1],
                workflow_update(ticket.ticket_id, target, recommendation),
            ),
            agent_runs=(
                *proposed.agent_runs,
                agent_run(
                    ticket.ticket_id,
                    "jioc-routing-agent",
                    _reason(codes),
                    safety_flags=codes if not automatic else (),
                    policy_version=ROUTING_POLICY_VERSION,
                    context_schema_version=context.schema_version,
                    input_hash=f"sha256:{context.requirement_revision}",
                    output_hash=provenance_hash(
                        {
                            "disposition": disposition,
                            "evidence_outcome": evidence_outcome,
                            "rationale_codes": list(codes),
                            "recommended_route": route.value,
                            "required_clarifications": list(questions),
                        }
                    ),
                ),
            ),
            timeline=updated_timeline,
        )
        if target == TicketState.COLLECT_CHOICE:
            proposed = append_collect_choice_handoff(
                proposed, collect_choice_handoff(ticket.ticket_id, JIOC_AGENT_PRINCIPAL)
            )
        return self._tickets.mutations.save_audited_with_outbox_if_current(
            ticket,
            proposed,
            _event_type(disposition),
            JIOC_AGENT_PRINCIPAL,
            {
                "ticket_id": str(ticket.ticket_id),
                "route": route.value,
                "disposition": disposition,
                "policy_version": ROUTING_POLICY_VERSION,
            },
            (routing_critique_intent(context, decision, rfa_review, cm_review, target),),
        )

    def defer_to_manager(
        self, ticket_id: UUID, reason: str = "routing_automation_disabled"
    ) -> TicketRecord:
        """Keep disabled automation out of the decision while preserving a human path."""

        ticket = self._ticket(ticket_id)
        if ticket.state != TicketState.JIOC_ROUTING_PENDING:
            return ticket
        target = TicketState.JIOC_REVIEW
        proposed = replace(
            ticket,
            state=target,
            timeline=(
                *ticket.timeline,
                timeline(
                    ticket.ticket_id,
                    JIOC_AGENT_PRINCIPAL,
                    "jioc_routing_referred_to_manager",
                    _customer_safe_timeline(target),
                ),
            ),
        )
        return self._tickets.mutations.save_audited_if_current(
            ticket,
            proposed,
            "jioc_routing_referred_to_manager",
            JIOC_AGENT_PRINCIPAL,
            {"ticket_id": str(ticket.ticket_id), "reason": reason},
        )

    def _ticket(self, ticket_id: UUID) -> TicketRecord:
        ticket = next(
            (
                item
                for item in self._tickets.tickets.assignment_snapshot()
                if item.ticket_id == ticket_id
            ),
            None,
        )
        if ticket is None:
            raise LookupError("Ticket was not found for JIOC routing.")
        return ticket


def _shadow_review(
    ticket: TicketRecord,
    rfa_review: RfaCapabilityReview,
    cm_review: CmCapabilityReview,
    recommendation: RouteRecommendation,
) -> TicketRecord:
    """Persist internal evidence only, without requester-facing handoffs."""

    target = TicketState.JIOC_REVIEW
    return replace(
        ticket,
        state=target,
        rfa_reviews=(*ticket.rfa_reviews, rfa_review),
        cm_reviews=(*ticket.cm_reviews, cm_review),
        route_recommendations=(*ticket.route_recommendations, recommendation),
        agent_runs=(
            *ticket.agent_runs,
            *review_agent_runs(ticket, rfa_review, cm_review, recommendation),
        ),
        workflow_plan_updates=(
            *ticket.workflow_plan_updates,
            workflow_update(ticket.ticket_id, target, recommendation),
        ),
    )


def _event_type(disposition: str) -> str:
    return {
        "auto_applied": "jioc_agent_route_applied",
        "clarification": "jioc_agent_clarification_requested",
        "manager_review": "jioc_agent_escalated",
        "shadow_recommendation": "jioc_agent_shadow_recommendation_recorded",
    }[disposition]


def _reason(codes: tuple[str, ...]) -> str:
    return "JIOC routing policy: " + ", ".join(code.replace("_", " ") for code in codes) + "."


def _customer_safe_timeline(target: TicketState) -> str:
    if target == TicketState.ANALYST_ASSIGNMENT:
        return "The request was routed for assessment team assignment."
    if target == TicketState.COLLECT_CHOICE:
        return "The request requires collection; a customer collection choice is needed."
    if target == TicketState.INFO_REQUIRED:
        return "More information is required before the request can be routed."
    return "The routing agent referred the request for JIOC manager review."
