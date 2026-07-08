from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from coeus.api.dependencies import (
    get_csrf_validated_session,
    get_current_session,
    get_similar_request_service,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.schemas.similar_requests import (
    SimilarRequestJoinResponse,
    SimilarRequestListResponse,
    SimilarRequestNoticeResponse,
    SimilarRequestResponse,
)
from coeus.services.similar_request_scoring import SimilarRequestMatch
from coeus.services.similar_requests import SimilarRequestService

router = APIRouter(prefix="/similar-requests", tags=["similar requests"])


@router.get("/tickets/{ticket_id}", response_model=SimilarRequestNoticeResponse)
async def customer_notice(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    service: Annotated[SimilarRequestService, Depends(get_similar_request_service)],
) -> SimilarRequestNoticeResponse:
    matches = service.customer_notice(authenticated.user, ticket_id)
    return SimilarRequestNoticeResponse(
        matches=[_match_response(match) for match in matches],
    )


@router.post(
    "/tickets/{ticket_id}/join/{related_ticket_id}", response_model=SimilarRequestJoinResponse
)
async def join_customer_match(
    ticket_id: UUID,
    related_ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    service: Annotated[SimilarRequestService, Depends(get_similar_request_service)],
) -> SimilarRequestJoinResponse:
    ticket = service.join_visible_match(authenticated.user, ticket_id, related_ticket_id)
    return SimilarRequestJoinResponse(joined_ticket_id=ticket.ticket_id, reference=ticket.reference)


@router.get("/routing/{ticket_id}", response_model=SimilarRequestListResponse)
async def manager_matches(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    service: Annotated[SimilarRequestService, Depends(get_similar_request_service)],
) -> SimilarRequestListResponse:
    return SimilarRequestListResponse(
        matches=[
            _match_response(match)
            for match in service.manager_matches(authenticated.user, ticket_id)
        ]
    )


@router.post(
    "/routing/{ticket_id}/link/{related_ticket_id}", response_model=SimilarRequestListResponse
)
async def link_related_ticket(
    ticket_id: UUID,
    related_ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    service: Annotated[SimilarRequestService, Depends(get_similar_request_service)],
) -> SimilarRequestListResponse:
    service.link_related(authenticated.user, ticket_id, related_ticket_id)
    return SimilarRequestListResponse(
        matches=[
            _match_response(match)
            for match in service.manager_matches(authenticated.user, ticket_id)
        ]
    )


def _match_response(match: SimilarRequestMatch) -> SimilarRequestResponse:
    return SimilarRequestResponse(
        ticket_id=match.ticket_id,
        reference=match.reference,
        title=match.title,
        state=match.state.value,
        score=match.score,
        reasons=list(match.reasons),
        already_linked=match.already_linked,
    )
