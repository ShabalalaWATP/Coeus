"""Pure, fail-closed JIOC routing policy decisions."""

from coeus.domain.enums import TicketState
from coeus.domain.jioc_routing import JiocRoutingContext
from coeus.domain.tickets import CmCapabilityReview, RfaCapabilityReview, RoutingRoute, TicketRecord
from coeus.services.jioc_routing_context import capacity_status, evidence_failures

Decision = tuple[str, RoutingRoute, float, tuple[str, ...], tuple[str, ...]]


def decide(
    ticket: TicketRecord,
    context: JiocRoutingContext,
    rfa: RfaCapabilityReview,
    cm: CmCapabilityReview,
) -> Decision:
    evidence_codes = evidence_failures(context)
    if evidence_codes:
        return "manager_review", advisory_route(rfa, cm), 0.0, evidence_codes, ()
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
            advisory_route(rfa, cm),
            max(rfa.confidence, cm.confidence),
            ("risk_review_required",),
            (),
        )
    if rfa.can_satisfy and cm.can_satisfy:
        return (
            "manager_review",
            advisory_route(rfa, cm),
            max(rfa.confidence, cm.confidence),
            ("conflicting_route_signals",),
            (),
        )
    if cm.can_satisfy:
        return _capacity_decision(
            RoutingRoute.CM,
            cm.suggested_collection_team_id,
            cm.confidence,
            context,
            "new_collection_required",
        )
    if rfa.can_satisfy:
        return _capacity_decision(
            RoutingRoute.RFA,
            rfa.suggested_team_id,
            rfa.confidence,
            context,
            "existing_information_assessment",
        )
    return (
        "manager_review",
        RoutingRoute.CLARIFICATION,
        max(rfa.confidence, cm.confidence),
        ("insufficient_route_evidence",),
        (),
    )


def candidate_team_ids(rfa: RfaCapabilityReview, cm: CmCapabilityReview) -> tuple[str, ...]:
    values = (
        rfa.suggested_team_id,
        cm.suggested_collection_team_id,
        *(item.team_id for item in rfa.candidate_teams),
        *(item.team_id for item in cm.candidate_teams),
    )
    return tuple(dict.fromkeys(value for value in values if value))


def evidence_outcome(rfa: RfaCapabilityReview, cm: CmCapabilityReview, disposition: str) -> str:
    if rfa.can_satisfy and cm.can_satisfy:
        return "conflicting"
    if rfa.can_satisfy:
        return "eligible_rfa"
    if cm.can_satisfy:
        return "eligible_cm"
    if disposition == "clarification":
        return "clarification_required"
    return "insufficient_evidence"


def target_state(disposition: str, route: RoutingRoute) -> TicketState:
    if disposition in {"manager_review", "shadow_recommendation"}:
        return TicketState.JIOC_REVIEW
    if disposition == "clarification" or route == RoutingRoute.CLARIFICATION:
        return TicketState.INFO_REQUIRED
    return (
        TicketState.COLLECT_CHOICE if route == RoutingRoute.CM else TicketState.ANALYST_ASSIGNMENT
    )


def advisory_route(rfa: RfaCapabilityReview, cm: CmCapabilityReview) -> RoutingRoute:
    if cm.can_satisfy and cm.confidence >= rfa.confidence:
        return RoutingRoute.CM
    if rfa.can_satisfy:
        return RoutingRoute.RFA
    return RoutingRoute.CLARIFICATION


def _capacity_decision(
    route: RoutingRoute,
    team_id: str | None,
    evidence_strength: float,
    context: JiocRoutingContext,
    success_code: str,
) -> Decision:
    status = capacity_status(context, team_id)
    if status != "available":
        code = "team_capacity_unavailable" if status == "unavailable" else "team_capacity_missing"
        return "manager_review", route, evidence_strength, (code,), ()
    return "auto_applied", route, evidence_strength, (success_code,), ()
