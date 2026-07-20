"""Autonomous, policy-constrained JIOC routing with a human exception queue."""

from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from coeus.domain.enums import TicketState
from coeus.domain.jioc_routing import JiocRoutingContext, JiocRoutingDecision
from coeus.domain.tickets import (
    CmCapabilityReview,
    RfaCapabilityReview,
    RoutingRoute,
    TicketRecord,
)
from coeus.services.capability_catalogue import CapabilityCatalogue
from coeus.services.orchestration_handoff import (
    append_collect_choice_handoff,
    collect_choice_handoff,
)
from coeus.services.routing_agents import CmCapabilityAgent, RfaCapabilityAgent
from coeus.services.routing_records import (
    agent_run,
    latest_recommendation,
    timeline,
    workflow_update,
)
from coeus.services.routing_review_updates import build_routing_review_update
from coeus.services.tickets import TicketServices

JIOC_AGENT_PRINCIPAL = UUID("00000000-0000-0000-0000-000000000002")
CONTEXT_SCHEMA_VERSION = "jioc-routing-context-v1"
POLICY_VERSION = "jioc-routing-policy-v1"
AUTO_ROUTE_CONFIDENCE = 0.80


class JiocRoutingAgentService:
    """Apply routine route decisions and abstain to JIOC manager review."""

    def __init__(self, tickets: TicketServices) -> None:
        self._tickets = tickets
        catalogue = CapabilityCatalogue()
        self._rfa_agent = RfaCapabilityAgent(catalogue)
        self._cm_agent = CmCapabilityAgent(catalogue)

    def route(self, ticket_id: UUID) -> TicketRecord:
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
        if ticket.state != TicketState.JIOC_ROUTING_PENDING:
            return ticket

        context = _context(ticket)
        rfa_review = self._rfa_agent.review(ticket)
        cm_review = self._cm_agent.review(ticket)
        disposition, route, confidence, codes, questions = _decide(
            ticket, context, rfa_review, cm_review
        )
        automatic = disposition == "auto_applied"
        rfa_review = replace(rfa_review, manager_review_required=not automatic)
        cm_review = replace(cm_review, manager_review_required=not automatic)
        review = build_routing_review_update(ticket, JIOC_AGENT_PRINCIPAL, rfa_review, cm_review)
        recommendation = latest_recommendation(review.proposed)
        if recommendation.recommended_route != route:
            recommendation = replace(
                recommendation,
                recommended_route=route,
                reasoning_summary=_reason(codes),
            )
            review = replace(
                review,
                proposed=replace(
                    review.proposed,
                    route_recommendations=(
                        *review.proposed.route_recommendations[:-1],
                        recommendation,
                    ),
                ),
            )
        decision = JiocRoutingDecision(
            decision_id=uuid4(),
            ticket_id=ticket.ticket_id,
            context_id=context.context_id,
            recommended_route=route.value,
            disposition=disposition,
            confidence=confidence,
            rationale_codes=codes,
            required_clarifications=questions,
            policy_version=POLICY_VERSION,
            created_at=datetime.now(UTC),
        )
        target = _target(disposition, route)
        proposed = replace(
            review.proposed,
            state=target,
            jioc_routing_contexts=(*ticket.jioc_routing_contexts, context),
            jioc_routing_decisions=(*ticket.jioc_routing_decisions, decision),
            workflow_plan_updates=(
                *review.proposed.workflow_plan_updates[:-1],
                workflow_update(ticket.ticket_id, target, recommendation),
            ),
            agent_runs=(
                *review.proposed.agent_runs,
                agent_run(ticket.ticket_id, "jioc-routing-agent", _reason(codes)),
            ),
            timeline=(
                *review.proposed.timeline,
                timeline(
                    ticket.ticket_id,
                    JIOC_AGENT_PRINCIPAL,
                    _event_type(disposition),
                    _customer_safe_timeline(target),
                ),
            ),
        )
        if target == TicketState.COLLECT_CHOICE:
            proposed = append_collect_choice_handoff(
                proposed, collect_choice_handoff(ticket.ticket_id, JIOC_AGENT_PRINCIPAL)
            )
        return self._tickets.mutations.save_audited_if_current(
            ticket,
            proposed,
            _event_type(disposition),
            JIOC_AGENT_PRINCIPAL,
            {
                "ticket_id": str(ticket.ticket_id),
                "route": route.value,
                "disposition": disposition,
                "policy_version": POLICY_VERSION,
            },
        )


def _context(ticket: TicketRecord) -> JiocRoutingContext:
    metric = ticket.search_metrics[-1] if ticket.search_metrics else None
    intake = ticket.intake
    values = (
        intake.title,
        intake.description,
        intake.operational_question,
        intake.area_or_region,
        intake.time_period_start,
        intake.time_period_end,
        intake.priority,
        intake.deadline,
        intake.required_output_format,
        intake.known_context,
        intake.restrictions_or_caveats,
        intake.customer_success_criteria,
        intake.requesting_unit,
        intake.intelligence_disciplines,
        intake.supported_operation,
    )
    revision = sha256("\n".join(value or "" for value in values).encode()).hexdigest()
    return JiocRoutingContext(
        context_id=uuid4(),
        ticket_id=ticket.ticket_id,
        schema_version=CONTEXT_SCHEMA_VERSION,
        requirement_revision=revision,
        search_outcome=metric.outcome if metric else "missing",
        search_assurance=metric.assurance if metric else "missing",
        search_coverage=metric.coverage_status if metric else "missing",
        search_corpus_version=metric.corpus_version if metric else None,
        product_offer_statuses=tuple(
            f"{offer.product_id}:{offer.status.value}" for offer in ticket.product_offers
        ),
        active_work_search_completed=any(
            item.event_type == "active_work_search_completed" for item in ticket.timeline
        ),
        active_work_offer_statuses=tuple(
            f"{offer.ticket_id}:{offer.status}" for offer in ticket.active_work_offers
        ),
        priority=intake.priority,
        deadline=intake.deadline,
        required_output_format=intake.required_output_format,
        intelligence_disciplines=intake.intelligence_disciplines,
        area_or_region=intake.area_or_region,
        time_period_start=intake.time_period_start,
        time_period_end=intake.time_period_end,
        restrictions_present=bool((intake.restrictions_or_caveats or "").strip()),
        created_at=datetime.now(UTC),
    )


def _decide(
    ticket: TicketRecord,
    context: JiocRoutingContext,
    rfa: RfaCapabilityReview,
    cm: CmCapabilityReview,
) -> tuple[str, RoutingRoute, float, tuple[str, ...], tuple[str, ...]]:
    evidence_codes = _evidence_failures(ticket, context)
    if evidence_codes:
        return "manager_review", _advisory_route(rfa, cm), 0.0, evidence_codes, ()
    questions = tuple(dict.fromkeys((*rfa.required_clarifications, *cm.required_clarifications)))
    if questions:
        return (
            "clarification",
            RoutingRoute.CLARIFICATION,
            0.0,
            ("clarification_required",),
            questions,
        )
    if context.restrictions_present or rfa.risks or cm.risks:
        return (
            "manager_review",
            _advisory_route(rfa, cm),
            max(rfa.confidence, cm.confidence),
            ("risk_review_required",),
            (),
        )
    if cm.can_satisfy and cm.confidence >= AUTO_ROUTE_CONFIDENCE:
        return "auto_applied", RoutingRoute.CM, cm.confidence, ("new_collection_required",), ()
    if rfa.can_satisfy and rfa.confidence >= AUTO_ROUTE_CONFIDENCE:
        return (
            "auto_applied",
            RoutingRoute.RFA,
            rfa.confidence,
            ("existing_information_assessment",),
            (),
        )
    return (
        "manager_review",
        _advisory_route(rfa, cm),
        max(rfa.confidence, cm.confidence),
        ("low_route_confidence",),
        (),
    )


def _evidence_failures(ticket: TicketRecord, context: JiocRoutingContext) -> tuple[str, ...]:
    failures: list[str] = []
    if context.search_assurance != "definitive" or context.search_coverage != "complete":
        failures.append("product_search_not_definitive")
    if any(offer.status.value == "offered" for offer in ticket.product_offers):
        failures.append("product_offer_unresolved")
    if not context.active_work_search_completed:
        failures.append("active_work_search_missing")
    if any(offer.status == "offered" for offer in ticket.active_work_offers):
        failures.append("active_work_offer_unresolved")
    return tuple(failures)


def _advisory_route(rfa: RfaCapabilityReview, cm: CmCapabilityReview) -> RoutingRoute:
    if cm.can_satisfy and cm.confidence >= rfa.confidence:
        return RoutingRoute.CM
    if rfa.can_satisfy:
        return RoutingRoute.RFA
    return RoutingRoute.CLARIFICATION


def _target(disposition: str, route: RoutingRoute) -> TicketState:
    if disposition == "manager_review":
        return TicketState.JIOC_REVIEW
    if disposition == "clarification" or route == RoutingRoute.CLARIFICATION:
        return TicketState.INFO_REQUIRED
    return (
        TicketState.COLLECT_CHOICE if route == RoutingRoute.CM else TicketState.ANALYST_ASSIGNMENT
    )


def _event_type(disposition: str) -> str:
    return {
        "auto_applied": "jioc_agent_route_applied",
        "clarification": "jioc_agent_clarification_requested",
        "manager_review": "jioc_agent_escalated",
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
