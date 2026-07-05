from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from coeus.api.dependencies import (
    get_csrf_validated_session,
    get_current_session,
    get_feedback_analytics_service,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.qc import FeedbackSubmission
from coeus.schemas.feedback_analytics import (
    FeedbackRequestListResponse,
    FeedbackRequestResponse,
    FeedbackSubmissionRequest,
    FeedbackSubmissionResponse,
)
from coeus.services.feedback_analytics import (
    FeedbackAnalyticsService,
    FeedbackRequestView,
    FeedbackSubmissionInput,
)

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get("/requests", response_model=FeedbackRequestListResponse)
async def feedback_requests(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    service: Annotated[FeedbackAnalyticsService, Depends(get_feedback_analytics_service)],
) -> FeedbackRequestListResponse:
    return FeedbackRequestListResponse(
        requests=[
            _feedback_response(item) for item in service.list_feedback_requests(authenticated.user)
        ]
    )


@router.post("/requests/{request_id}/submit", response_model=FeedbackRequestResponse)
async def submit_feedback(
    request_id: UUID,
    payload: FeedbackSubmissionRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    service: Annotated[FeedbackAnalyticsService, Depends(get_feedback_analytics_service)],
) -> FeedbackRequestResponse:
    view = service.submit_feedback(
        authenticated.user,
        request_id,
        FeedbackSubmissionInput(
            rating=payload.rating,
            comment=payload.comment,
            follow_up_requested=payload.follow_up_requested,
        ),
    )
    return _feedback_response(view)


def _feedback_response(view: FeedbackRequestView) -> FeedbackRequestResponse:
    request = view.request
    return FeedbackRequestResponse(
        request_id=request.request_id,
        ticket_id=request.ticket_id,
        ticket_reference=view.ticket.reference,
        product_id=request.product_id,
        product_title=view.product_title,
        status=request.status.value,
        created_at=request.created_at,
        submission=_submission_response(view.submission),
    )


def _submission_response(
    submission: FeedbackSubmission | None,
) -> FeedbackSubmissionResponse | None:
    if submission is None:
        return None
    return FeedbackSubmissionResponse(
        submission_id=submission.submission_id,
        request_id=submission.request_id,
        rating=submission.rating,
        comment=submission.comment,
        follow_up_requested=submission.follow_up_requested,
        created_at=submission.created_at,
    )
