from collections.abc import Iterable

from coeus.domain.capabilities import CapabilityTeam
from coeus.domain.tickets import (
    ClarificationRequest,
    CmCapabilityReview,
    ManagerRoutingDecision,
    RfaCapabilityReview,
    RouteRecommendation,
    TicketRecord,
    WorkflowPlanUpdate,
)
from coeus.schemas.routing import (
    CapabilityCatalogueResponse,
    CapabilityTeamResponse,
    ClarificationRequestResponse,
    CmCapabilityReviewResponse,
    ManagerDecisionResponse,
    RfaCapabilityReviewResponse,
    RouteRecommendationResponse,
    RoutingQueueResponse,
    RoutingStatsResponse,
    RoutingTicketResponse,
    WorkflowPlanUpdateResponse,
)
from coeus.services.routing_stats import RoutingStats


def routing_queue_response(
    tickets: Iterable[TicketRecord], stats: RoutingStats
) -> RoutingQueueResponse:
    return RoutingQueueResponse(
        tickets=[ticket_response(ticket) for ticket in tickets],
        stats=stats_response(stats),
    )


def capability_catalogue_response(
    teams: Iterable[CapabilityTeam],
) -> CapabilityCatalogueResponse:
    return CapabilityCatalogueResponse(teams=[_capability_team_response(team) for team in teams])


def ticket_response(ticket: TicketRecord) -> RoutingTicketResponse:
    return RoutingTicketResponse(
        ticket_id=ticket.ticket_id,
        reference=ticket.reference,
        requester_user_id=ticket.requester_user_id,
        state=ticket.state.value,
        title=ticket.intake.title or "Untitled requirement",
        priority=ticket.intake.priority,
        rfa_review=_rfa_response(ticket.rfa_reviews[-1]) if ticket.rfa_reviews else None,
        cm_review=_cm_response(ticket.cm_reviews[-1]) if ticket.cm_reviews else None,
        recommendation=_recommendation_response(ticket.route_recommendations[-1])
        if ticket.route_recommendations
        else None,
        clarifications=[_clarification_response(item) for item in ticket.clarification_requests],
        agent_runs=[run.agent_name for run in ticket.agent_runs],
        manager_decisions=[_decision_response(item) for item in ticket.manager_decisions],
        workflow_plan_updates=[
            _workflow_update_response(item) for item in ticket.workflow_plan_updates
        ],
    )


def stats_response(stats: RoutingStats) -> RoutingStatsResponse:
    return RoutingStatsResponse(
        route_assessment_count=stats.route_assessment_count,
        rfa_review_count=stats.rfa_review_count,
        cm_review_count=stats.cm_review_count,
        clarification_count=stats.clarification_count,
        analyst_assignment_count=stats.analyst_assignment_count,
        rfa_acceptance_rate=stats.rfa_acceptance_rate,
        cm_fallback_rate=stats.cm_fallback_rate,
    )


def _capability_team_response(team: CapabilityTeam) -> CapabilityTeamResponse:
    return CapabilityTeamResponse(
        team_id=team.team_id,
        name=team.name,
        department=team.department.value,
        keywords=sorted(team.keywords),
        work_packages=list(team.work_packages),
        source_labels=list(team.source_labels),
    )


def _rfa_response(review: RfaCapabilityReview) -> RfaCapabilityReviewResponse:
    return RfaCapabilityReviewResponse(
        review_id=review.review_id,
        can_satisfy=review.can_satisfy,
        confidence=review.confidence,
        required_clarifications=list(review.required_clarifications),
        suggested_work_packages=list(review.suggested_work_packages),
        suggested_team_id=review.suggested_team_id,
        suggested_team_name=review.suggested_team_name,
        estimated_effort=review.estimated_effort,
        risks=list(review.risks),
        manager_review_required=review.manager_review_required,
        reasoning_summary=review.reasoning_summary,
        created_at=review.created_at,
    )


def _cm_response(review: CmCapabilityReview) -> CmCapabilityReviewResponse:
    return CmCapabilityReviewResponse(
        review_id=review.review_id,
        can_satisfy=review.can_satisfy,
        confidence=review.confidence,
        required_clarifications=list(review.required_clarifications),
        suggested_collection_route=review.suggested_collection_route,
        suggested_collection_team_id=review.suggested_collection_team_id,
        suggested_collection_team_name=review.suggested_collection_team_name,
        suggested_collection_sources=list(review.suggested_collection_sources),
        estimated_effort=review.estimated_effort,
        risks=list(review.risks),
        manager_review_required=review.manager_review_required,
        reasoning_summary=review.reasoning_summary,
        created_at=review.created_at,
    )


def _recommendation_response(
    recommendation: RouteRecommendation,
) -> RouteRecommendationResponse:
    return RouteRecommendationResponse(
        recommendation_id=recommendation.recommendation_id,
        recommended_route=recommendation.recommended_route.value,
        reasoning_summary=recommendation.reasoning_summary,
        created_at=recommendation.created_at,
    )


def _clarification_response(
    clarification: ClarificationRequest,
) -> ClarificationRequestResponse:
    return ClarificationRequestResponse(
        clarification_id=clarification.clarification_id,
        route=clarification.route.value,
        reason=clarification.reason,
        questions=list(clarification.questions),
        requested_by_user_id=clarification.requested_by_user_id,
        created_at=clarification.created_at,
    )


def _decision_response(decision: ManagerRoutingDecision) -> ManagerDecisionResponse:
    return ManagerDecisionResponse(
        decision_id=decision.decision_id,
        route=decision.route.value,
        status=decision.status.value,
        reason=decision.reason,
        override_reason=decision.override_reason,
        actor_user_id=decision.actor_user_id,
        created_at=decision.created_at,
    )


def _workflow_update_response(update: WorkflowPlanUpdate) -> WorkflowPlanUpdateResponse:
    return WorkflowPlanUpdateResponse(
        update_id=update.update_id,
        title=update.title,
        owner_role=update.owner_role,
        status=update.status,
        note=update.note,
        created_at=update.created_at,
    )
