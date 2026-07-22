from dataclasses import dataclass, replace
from uuid import UUID

from coeus.domain.enums import TicketState
from coeus.domain.tickets import CmCapabilityReview, RfaCapabilityReview, TicketRecord
from coeus.services.orchestration_handoff import (
    ClarificationHandoff,
    agent_clarification_handoff,
    append_handoff,
)
from coeus.services.routing_records import (
    recommend_route,
    review_agent_runs,
    state_for_recommendation,
    timeline,
    workflow_update,
)


@dataclass(frozen=True)
class RoutingReviewUpdate:
    proposed: TicketRecord
    target_state: TicketState
    metadata: dict[str, str]


def build_routing_review_update(
    ticket: TicketRecord,
    actor_user_id: UUID,
    rfa_review: RfaCapabilityReview,
    cm_review: CmCapabilityReview,
) -> RoutingReviewUpdate:
    recommendation = recommend_route(ticket.ticket_id, rfa_review, cm_review)
    target_state = state_for_recommendation(recommendation)
    handoff: ClarificationHandoff | None = agent_clarification_handoff(
        ticket.ticket_id,
        actor_user_id,
        recommendation.reasoning_summary,
        (*rfa_review.required_clarifications, *cm_review.required_clarifications),
    )
    if target_state != TicketState.INFO_REQUIRED:
        handoff = None
    proposed = append_handoff(
        replace(
            ticket,
            state=target_state,
            rfa_reviews=(*ticket.rfa_reviews, rfa_review),
            cm_reviews=(*ticket.cm_reviews, cm_review),
            route_recommendations=(*ticket.route_recommendations, recommendation),
            agent_runs=(
                *ticket.agent_runs,
                *review_agent_runs(ticket, rfa_review, cm_review, recommendation),
            ),
            workflow_plan_updates=(
                *ticket.workflow_plan_updates,
                workflow_update(ticket.ticket_id, target_state, recommendation),
            ),
            timeline=(
                *ticket.timeline,
                timeline(
                    ticket.ticket_id,
                    actor_user_id,
                    "route_reviews_completed",
                    recommendation.reasoning_summary,
                ),
            ),
        ),
        handoff,
    )
    metadata = {
        "ticket_id": str(ticket.ticket_id),
        "recommended_route": recommendation.recommended_route.value,
    }
    if rfa_review.suggested_team_name:
        metadata["rfa_team"] = rfa_review.suggested_team_name
    if cm_review.suggested_collection_team_name:
        metadata["cm_team"] = cm_review.suggested_collection_team_name
    return RoutingReviewUpdate(proposed=proposed, target_state=target_state, metadata=metadata)
