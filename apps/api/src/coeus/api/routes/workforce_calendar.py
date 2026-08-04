"""Personal and explicitly authorised manager calendar routes."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from coeus.api.dependencies import get_csrf_validated_session, get_current_session
from coeus.api.organisation_dependencies import get_workforce_calendar
from coeus.api.workforce_calendar_contracts import (
    call_calendar,
    event_payload,
    mutation_request,
    occurrence_payload,
    preview_response,
    projection_response,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.workforce_calendar import (
    CalendarCommitmentResponse,
    CalendarMutationCommand,
)
from coeus.schemas.workforce_calendar import (
    CalendarCommandPayload,
    CalendarCommitmentListResponse,
    CalendarCommitmentPayload,
    CalendarCommitmentResponsePayload,
    CalendarEventListResponse,
    CalendarMutationPayload,
    CalendarMutationResultResponse,
    CalendarPreviewResponse,
    CalendarProjectionResponse,
)
from coeus.services.workforce_calendar import WorkforceCalendarService

router = APIRouter(prefix="/calendar", tags=["workforce calendar"])
CalendarDep = Annotated[WorkforceCalendarService, Depends(get_workforce_calendar)]
SessionDep = Annotated[AuthenticatedSession, Depends(get_current_session)]
CsrfSessionDep = Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)]


@router.get("/commitments/me", response_model=CalendarCommitmentListResponse)
async def personal_commitments(
    authenticated: SessionDep,
    service: CalendarDep,
) -> CalendarCommitmentListResponse:
    commitments = call_calendar(lambda: service.commitments(authenticated.user.user_id))
    return CalendarCommitmentListResponse(
        commitments=[
            CalendarCommitmentPayload(
                event=event_payload(item.event),
                responseState=item.response_state,
                responseVersion=item.response_version,
                notifiedAt=item.notified_at,
                respondedAt=item.responded_at,
            )
            for item in commitments
        ]
    )


@router.post("/commitments/{event_id}/responses", response_model=CalendarCommitmentPayload)
async def respond_to_commitment(
    event_id: UUID,
    payload: CalendarCommitmentResponsePayload,
    authenticated: CsrfSessionDep,
    service: CalendarDep,
) -> CalendarCommitmentPayload:
    item = call_calendar(
        lambda: service.respond_to_commitment(
            authenticated.user.user_id,
            CalendarCommitmentResponse(
                event_id,
                authenticated.user.user_id,
                payload.state,
                payload.expected_version,
                payload.reason,
            ),
        )
    )
    return CalendarCommitmentPayload(
        event=event_payload(item.event),
        responseState=item.response_state,
        responseVersion=item.response_version,
        notifiedAt=item.notified_at,
        respondedAt=item.responded_at,
    )


@router.get("/me", response_model=CalendarEventListResponse)
async def personal_calendar(
    authenticated: SessionDep,
    service: CalendarDep,
    window_start: Annotated[datetime, Query(alias="windowStart")],
    window_end: Annotated[datetime, Query(alias="windowEnd")],
) -> CalendarEventListResponse:
    events = call_calendar(
        lambda: service.personal_calendar(authenticated.user.user_id, window_start, window_end)
    )
    return CalendarEventListResponse(events=[occurrence_payload(event) for event in events])


@router.get("/units/{unit_id}", response_model=CalendarProjectionResponse)
async def team_calendar_projection(
    unit_id: UUID,
    authenticated: SessionDep,
    service: CalendarDep,
    window_start: Annotated[datetime, Query(alias="windowStart")],
    window_end: Annotated[datetime, Query(alias="windowEnd")],
    include_descendants: Annotated[bool, Query(alias="includeDescendants")] = False,
    view: Annotated[Literal["availability", "detail"], Query()] = "availability",
) -> CalendarProjectionResponse:
    projection = call_calendar(
        lambda: service.team_projection(
            authenticated.user.user_id,
            unit_id,
            window_start,
            window_end,
            include_descendants=include_descendants,
            request_detail=view == "detail",
        )
    )
    return projection_response(projection)


@router.post("/previews", response_model=CalendarPreviewResponse)
async def preview_calendar_change(
    payload: CalendarMutationPayload,
    authenticated: CsrfSessionDep,
    service: CalendarDep,
) -> CalendarPreviewResponse:
    request = call_calendar(lambda: mutation_request(payload))
    preview = call_calendar(lambda: service.preview(request, authenticated.user.user_id))
    return preview_response(preview)


@router.post("/commands", response_model=CalendarMutationResultResponse)
async def execute_calendar_change(
    payload: CalendarCommandPayload,
    authenticated: CsrfSessionDep,
    service: CalendarDep,
) -> CalendarMutationResultResponse:
    command = call_calendar(
        lambda: CalendarMutationCommand(
            payload.command_id,
            payload.idempotency_key,
            authenticated.user.user_id,
            mutation_request(payload.request),
            payload.preview_hash,
        )
    )
    result = call_calendar(lambda: service.execute(command))
    return CalendarMutationResultResponse(**vars(result))
