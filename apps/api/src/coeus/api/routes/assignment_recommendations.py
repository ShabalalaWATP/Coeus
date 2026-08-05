"""Manager preview and acceptance routes for deterministic assignment advice."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from coeus.api.assignment_recommendation_dependencies import (
    get_assignment_recommendation_service,
)
from coeus.api.dependencies import (
    get_analyst_workflow_service,
    get_csrf_validated_session,
)
from coeus.api.presenters.analyst import task_response
from coeus.domain.assignment_recommendations import AcceptRecommendationRequest
from coeus.domain.auth import AuthenticatedSession
from coeus.schemas.analyst import AnalystTaskResponse
from coeus.schemas.assignment_recommendations import (
    AssignmentRecommendationAcceptRequest,
    AssignmentRecommendationCandidateResponse,
    AssignmentRecommendationPreviewRequest,
    AssignmentRecommendationPreviewResponse,
)
from coeus.services.analyst_workflow import AnalystWorkflowService
from coeus.services.assignment_recommendations import AssignmentRecommendationService

router = APIRouter(prefix="/analyst/tasks", tags=["analyst"])


@router.post(
    "/{ticket_id}/assignment-recommendations/preview",
    response_model=AssignmentRecommendationPreviewResponse,
)
async def preview_assignment_recommendation(
    ticket_id: UUID,
    payload: AssignmentRecommendationPreviewRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    service: Annotated[
        AssignmentRecommendationService, Depends(get_assignment_recommendation_service)
    ],
) -> AssignmentRecommendationPreviewResponse:
    preview = service.preview(
        authenticated.user,
        ticket_id,
        payload.effort_min_minutes,
        payload.effort_max_minutes,
        payload.deadline,
        tuple(payload.capability_ids),
        payload.unit_id,
    )
    display_names = service.candidate_display_names(authenticated.user, ticket_id, preview)
    return AssignmentRecommendationPreviewResponse(
        recommendation_id=preview.recommendation_id,
        estimate_id=preview.estimate_id,
        estimate_version=preview.estimate_version,
        hold_id=preview.hold_id,
        preview_hash=preview.preview_hash,
        expires_at=preview.expires_at,
        candidates=[
            AssignmentRecommendationCandidateResponse(
                unit_id=item.unit_id,
                analyst_user_id=item.analyst_user_id,
                display_name=display_names[item.analyst_user_id],
                rank=item.rank,
                assignable_minutes=item.assignable_minutes,
                active_wip=item.active_wip,
                explanation_codes=[code.value for code in item.explanation_codes],
            )
            for item in preview.candidates
        ],
        exclusion_counts={code.value: count for code, count in preview.exclusion_counts},
    )


@router.post(
    "/{ticket_id}/assignment-recommendations/accept",
    response_model=AnalystTaskResponse,
)
async def accept_assignment_recommendation(
    ticket_id: UUID,
    payload: AssignmentRecommendationAcceptRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    service: Annotated[
        AssignmentRecommendationService, Depends(get_assignment_recommendation_service)
    ],
    analyst: Annotated[AnalystWorkflowService, Depends(get_analyst_workflow_service)],
) -> AnalystTaskResponse:
    ticket = service.accept(
        authenticated.user,
        ticket_id,
        AcceptRecommendationRequest(
            payload.recommendation_id,
            payload.preview_hash,
            payload.selected_unit_id,
            payload.selected_analyst_user_id,
            payload.override_reason,
        ),
        tuple(payload.work_packages),
    )
    return task_response(ticket, authenticated.user, analyst)
