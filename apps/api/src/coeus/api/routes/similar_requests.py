from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from coeus.api.dependencies import (
    get_csrf_validated_session,
    get_current_session,
    get_search_admission,
    get_similar_request_service,
)
from coeus.api.presenters.tickets import to_ticket_response
from coeus.api.workflow_dependencies import get_active_work_discovery_service
from coeus.application.ports.admission import ResourceAdmission
from coeus.domain.auth import AuthenticatedSession
from coeus.schemas.similar_requests import (
    SimilarRequestDuplicateRequest,
    SimilarRequestJoinResponse,
    SimilarRequestListResponse,
    SimilarRequestNoticeResponse,
    SimilarRequestResponse,
)
from coeus.schemas.tickets import TicketResponse
from coeus.services.active_work_discovery import ActiveWorkDiscoveryService
from coeus.services.similar_request_scoring import SimilarRequestMatch
from coeus.services.similar_requests import SimilarRequestService

router = APIRouter(prefix="/similar-requests", tags=["similar requests"])


@router.get("/tickets/{ticket_id}", response_model=SimilarRequestNoticeResponse)
def customer_notice(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    service: Annotated[ActiveWorkDiscoveryService, Depends(get_active_work_discovery_service)],
) -> SimilarRequestNoticeResponse:
    matches = service.offers(authenticated.user, ticket_id)
    return SimilarRequestNoticeResponse(
        matches=[_match_response(match) for match in matches],
    )


@router.post(
    "/tickets/{ticket_id}/join/{related_ticket_id}", response_model=SimilarRequestJoinResponse
)
def join_customer_match(
    ticket_id: UUID,
    related_ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    service: Annotated[ActiveWorkDiscoveryService, Depends(get_active_work_discovery_service)],
) -> SimilarRequestJoinResponse:
    ticket = service.join(authenticated.user, ticket_id, related_ticket_id)
    return SimilarRequestJoinResponse(joined_ticket_id=ticket.ticket_id, reference=ticket.reference)


@router.post("/tickets/{ticket_id}/continue", response_model=TicketResponse)
def continue_after_active_work(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    service: Annotated[ActiveWorkDiscoveryService, Depends(get_active_work_discovery_service)],
) -> TicketResponse:
    ticket = service.continue_new_tasking(authenticated.user, ticket_id)
    return to_ticket_response(ticket, authenticated.user)


@router.post("/tickets/{ticket_id}/retry", response_model=TicketResponse)
def retry_active_work_search(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    service: Annotated[ActiveWorkDiscoveryService, Depends(get_active_work_discovery_service)],
) -> TicketResponse:
    ticket = service.discover(authenticated, ticket_id)
    return to_ticket_response(ticket, authenticated.user)


@router.get("/routing/{ticket_id}", response_model=SimilarRequestListResponse)
def manager_matches(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    service: Annotated[SimilarRequestService, Depends(get_similar_request_service)],
    admission: Annotated[ResourceAdmission, Depends(get_search_admission)],
) -> SimilarRequestListResponse:
    with admission.reserve(authenticated.user.user_id):
        return SimilarRequestListResponse(
            matches=[
                _match_response(match)
                for match in service.manager_matches(authenticated.user, ticket_id)
            ]
        )


@router.post(
    "/routing/{ticket_id}/link/{related_ticket_id}", response_model=SimilarRequestListResponse
)
def link_related_ticket(
    ticket_id: UUID,
    related_ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    service: Annotated[SimilarRequestService, Depends(get_similar_request_service)],
    admission: Annotated[ResourceAdmission, Depends(get_search_admission)],
) -> SimilarRequestListResponse:
    with admission.reserve(authenticated.user.user_id):
        service.link_related(authenticated.user, ticket_id, related_ticket_id)
        match = service.manager_match(authenticated.user, ticket_id, related_ticket_id)
    return SimilarRequestListResponse(matches=[] if match is None else [_match_response(match)])


@router.post(
    "/routing/{ticket_id}/duplicate/{related_ticket_id}",
    response_model=SimilarRequestListResponse,
)
def mark_duplicate_ticket(
    ticket_id: UUID,
    related_ticket_id: UUID,
    payload: SimilarRequestDuplicateRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    service: Annotated[SimilarRequestService, Depends(get_similar_request_service)],
    admission: Annotated[ResourceAdmission, Depends(get_search_admission)],
) -> SimilarRequestListResponse:
    with admission.reserve(authenticated.user.user_id):
        service.mark_duplicate(
            authenticated.user,
            ticket_id,
            related_ticket_id,
            withdraw_source=payload.withdraw_source,
        )
        match = service.manager_match(authenticated.user, ticket_id, related_ticket_id)
    return SimilarRequestListResponse(matches=[] if match is None else [_match_response(match)])


def _match_response(match: SimilarRequestMatch) -> SimilarRequestResponse:
    return SimilarRequestResponse(
        ticket_id=match.ticket_id,
        reference=match.reference,
        title=match.title,
        state=match.state.value,
        score=match.score,
        reasons=list(match.reasons),
        already_linked=match.already_linked,
        already_marked_duplicate=match.already_marked_duplicate,
        request_kind=match.request_kind,
        approved_route=match.approved_route,
        assigned_team=match.assigned_team,
        requesting_unit=match.requesting_unit,
        supported_operation=match.supported_operation,
        time_period_start=match.time_period_start,
        time_period_end=match.time_period_end,
    )
