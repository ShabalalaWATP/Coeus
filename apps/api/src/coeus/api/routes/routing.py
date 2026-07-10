from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from coeus.api.dependencies import (
    get_csrf_validated_session,
    get_current_session,
    get_product_release_service,
    get_routing_service,
)
from coeus.api.presenters.routing import (
    capability_catalogue_response,
    routing_queue_response,
    stats_response,
    ticket_response,
)
from coeus.core.errors import AppError
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.tickets import RoutingRoute, TicketRecord
from coeus.schemas.routing import (
    CapabilityCatalogueResponse,
    RouteApprovalRequest,
    RouteClarificationRequest,
    RouteReasonRequest,
    RoutingQueueResponse,
    RoutingStatsResponse,
    RoutingTicketResponse,
)
from coeus.services.product_release import ProductReleaseService
from coeus.services.routing import RoutingService

router = APIRouter(prefix="/routing", tags=["routing"])

RELEASE_ROUTES = {"rfa": RoutingRoute.RFA, "cm": RoutingRoute.CM}
QUEUE_PAGE_SIZE = 25


def _release_route(route: str) -> RoutingRoute:
    resolved = RELEASE_ROUTES.get(route)
    if resolved is None:
        raise AppError(422, "route_invalid", "Route must be rfa or cm.")
    return resolved


def _queue_page(
    tickets: tuple[TicketRecord, ...], cursor: int, limit: int
) -> tuple[tuple[TicketRecord, ...], str | None]:
    page = tickets[cursor : cursor + limit]
    next_cursor = str(cursor + limit) if cursor + limit < len(tickets) else None
    return page, next_cursor


@router.get("/{route}/release-queue", response_model=RoutingQueueResponse)
async def release_queue(
    route: str,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    releases: Annotated[ProductReleaseService, Depends(get_product_release_service)],
    routing: Annotated[RoutingService, Depends(get_routing_service)],
    cursor: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=QUEUE_PAGE_SIZE)] = QUEUE_PAGE_SIZE,
) -> RoutingQueueResponse:
    tickets = releases.queue(authenticated.user, _release_route(route))
    page, next_cursor = _queue_page(tickets, cursor, limit)
    return routing_queue_response(page, routing.stats(authenticated.user), next_cursor)


@router.post("/{ticket_id}/release", response_model=RoutingTicketResponse)
def release_product(
    ticket_id: UUID,
    payload: RouteApprovalRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    releases: Annotated[ProductReleaseService, Depends(get_product_release_service)],
) -> RoutingTicketResponse:
    return ticket_response(
        releases.release(authenticated.user, ticket_id, _release_route(payload.route))
    )


@router.get("/rfa/queue", response_model=RoutingQueueResponse)
async def rfa_queue(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    routing: Annotated[RoutingService, Depends(get_routing_service)],
    cursor: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=QUEUE_PAGE_SIZE)] = QUEUE_PAGE_SIZE,
) -> RoutingQueueResponse:
    tickets = routing.rfa_queue(authenticated.user)
    page, next_cursor = _queue_page(tickets, cursor, limit)
    return routing_queue_response(page, routing.stats(authenticated.user), next_cursor)


@router.get("/cm/queue", response_model=RoutingQueueResponse)
async def cm_queue(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    routing: Annotated[RoutingService, Depends(get_routing_service)],
    cursor: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=QUEUE_PAGE_SIZE)] = QUEUE_PAGE_SIZE,
) -> RoutingQueueResponse:
    tickets = routing.cm_queue(authenticated.user)
    page, next_cursor = _queue_page(tickets, cursor, limit)
    return routing_queue_response(page, routing.stats(authenticated.user), next_cursor)


@router.get("/stats", response_model=RoutingStatsResponse)
async def routing_stats(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    routing: Annotated[RoutingService, Depends(get_routing_service)],
) -> RoutingStatsResponse:
    return stats_response(routing.stats(authenticated.user))


@router.get("/capability-catalogue", response_model=CapabilityCatalogueResponse)
async def capability_catalogue(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    routing: Annotated[RoutingService, Depends(get_routing_service)],
) -> CapabilityCatalogueResponse:
    return capability_catalogue_response(routing.capability_catalogue(authenticated.user))


@router.get("/{ticket_id}", response_model=RoutingTicketResponse)
async def routing_details(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    routing: Annotated[RoutingService, Depends(get_routing_service)],
) -> RoutingTicketResponse:
    return ticket_response(routing.details(authenticated.user, ticket_id))


@router.post("/{ticket_id}/run", response_model=RoutingTicketResponse)
async def run_route_reviews(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    routing: Annotated[RoutingService, Depends(get_routing_service)],
) -> RoutingTicketResponse:
    return ticket_response(routing.run_reviews(authenticated.user, ticket_id))


@router.post("/{ticket_id}/approve", response_model=RoutingTicketResponse)
async def approve_route(
    ticket_id: UUID,
    payload: RouteApprovalRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    routing: Annotated[RoutingService, Depends(get_routing_service)],
) -> RoutingTicketResponse:
    return ticket_response(
        routing.approve(
            authenticated.user,
            ticket_id,
            RoutingRoute(payload.route),
            payload.override_reason,
        )
    )


@router.post("/{ticket_id}/reject", response_model=RoutingTicketResponse)
async def reject_route(
    ticket_id: UUID,
    payload: RouteReasonRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    routing: Annotated[RoutingService, Depends(get_routing_service)],
) -> RoutingTicketResponse:
    return ticket_response(
        routing.reject(authenticated.user, ticket_id, RoutingRoute(payload.route), payload.reason)
    )


@router.post("/{ticket_id}/clarification", response_model=RoutingTicketResponse)
async def request_clarification(
    ticket_id: UUID,
    payload: RouteClarificationRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    routing: Annotated[RoutingService, Depends(get_routing_service)],
) -> RoutingTicketResponse:
    return ticket_response(
        routing.request_clarification(
            authenticated.user,
            ticket_id,
            RoutingRoute(payload.route),
            payload.reason,
            tuple(payload.questions),
        )
    )
