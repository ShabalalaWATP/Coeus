from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from coeus.api.dependencies import (
    get_access_services,
    get_analyst_workflow_service,
    get_csrf_validated_session,
    get_current_session,
    get_manager_approval_service,
    get_manager_queue_service,
    get_routing_service,
    get_team_availability_service,
    get_team_repository,
    get_ticket_services,
)
from coeus.api.presenters.analyst import task_response
from coeus.api.presenters.routing import (
    capability_catalogue_response,
    routing_queue_response,
    stats_response,
    ticket_response,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.tickets import RoutingRoute, TicketRecord
from coeus.repositories.teams import TeamRepository
from coeus.schemas.analyst import AnalystTaskResponse
from coeus.schemas.routing import (
    CapabilityCatalogueResponse,
    OversightAnalystResponse,
    OversightCountResponse,
    OversightTaskResponse,
    OversightTeamResponse,
    RouteApprovalRequest,
    RouteClarificationRequest,
    RouteReasonRequest,
    RoutingOversightResponse,
    RoutingQueueResponse,
    RoutingStatsResponse,
    RoutingTicketResponse,
)
from coeus.services.access import AccessServices
from coeus.services.analyst_workflow import AnalystWorkflowService
from coeus.services.manager_approval import ManagerApprovalService
from coeus.services.manager_queue import ManagerQueueService
from coeus.services.routing import RoutingService
from coeus.services.routing_oversight import RoutingOversightService
from coeus.services.team_availability import TeamAvailabilityService
from coeus.services.tickets import TicketServices

router = APIRouter(prefix="/routing", tags=["routing"])

QUEUE_PAGE_SIZE = 25


@router.get("/oversight", response_model=RoutingOversightResponse)
async def routing_oversight(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    tickets: Annotated[TicketServices, Depends(get_ticket_services)],
    teams: Annotated[TeamRepository, Depends(get_team_repository)],
    access: Annotated[AccessServices, Depends(get_access_services)],
    availability: Annotated[TeamAvailabilityService, Depends(get_team_availability_service)],
) -> RoutingOversightResponse:
    view = RoutingOversightService(tickets, teams, access.repository, availability).view(
        authenticated.user
    )
    return RoutingOversightResponse(
        counts_by_state=[
            OversightCountResponse(key=key, count=count) for key, count in view.counts_by_state
        ],
        counts_by_route=[
            OversightCountResponse(key=key, count=count) for key, count in view.counts_by_route
        ],
        teams=[
            OversightTeamResponse(
                team_id=item.team_id,
                name=item.name,
                kind=item.kind,
                active_members=item.active_members,
                available_members=item.available_members,
                live_task_count=item.live_task_count,
            )
            for item in view.teams
        ],
        analysts=[
            OversightAnalystResponse(
                user_id=item.user_id,
                display_name=item.display_name,
                team_ids=list(item.team_ids),
                live_task_count=item.live_task_count,
            )
            for item in view.analysts
        ],
        tasks=[
            OversightTaskResponse(
                ticket_id=item.ticket_id,
                reference=item.reference,
                state=item.state,
                route=item.route,
                team_id=item.team_id,
                team_name=item.team_name,
                analyst_count=item.analyst_count,
                work_package_count=item.work_package_count,
                completed_work_package_count=item.completed_work_package_count,
            )
            for item in view.tasks
        ],
    )


@router.get("/{ticket_id}/manager-work", response_model=AnalystTaskResponse)
async def manager_review_work(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    approvals: Annotated[ManagerApprovalService, Depends(get_manager_approval_service)],
    analyst: Annotated[AnalystWorkflowService, Depends(get_analyst_workflow_service)],
) -> AnalystTaskResponse:
    return task_response(
        approvals.review_work(authenticated.user, ticket_id), authenticated.user, analyst
    )


def _queue_page(
    tickets: tuple[TicketRecord, ...], cursor: int, limit: int
) -> tuple[tuple[TicketRecord, ...], str | None]:
    page = tickets[cursor : cursor + limit]
    next_cursor = str(cursor + limit) if cursor + limit < len(tickets) else None
    return page, next_cursor


@router.post("/{ticket_id}/manager-approval", response_model=RoutingTicketResponse)
async def manager_approve_work(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    approvals: Annotated[ManagerApprovalService, Depends(get_manager_approval_service)],
) -> RoutingTicketResponse:
    return ticket_response(approvals.approve(authenticated.user, ticket_id))


@router.post("/{ticket_id}/manager-rework", response_model=RoutingTicketResponse)
async def manager_return_for_rework(
    ticket_id: UUID,
    payload: RouteReasonRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    approvals: Annotated[ManagerApprovalService, Depends(get_manager_approval_service)],
) -> RoutingTicketResponse:
    return ticket_response(
        approvals.return_for_rework(authenticated.user, ticket_id, payload.reason)
    )


@router.get("/jioc/queue", response_model=RoutingQueueResponse)
async def jioc_queue(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    routing: Annotated[RoutingService, Depends(get_routing_service)],
    cursor: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=QUEUE_PAGE_SIZE)] = QUEUE_PAGE_SIZE,
) -> RoutingQueueResponse:
    tickets = routing.jioc_queue(authenticated.user)
    page, next_cursor = _queue_page(tickets, cursor, limit)
    return routing_queue_response(page, routing.stats(authenticated.user), next_cursor)


@router.get("/rfa/queue", response_model=RoutingQueueResponse)
async def rfa_queue(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    manager_queue: Annotated[ManagerQueueService, Depends(get_manager_queue_service)],
    routing: Annotated[RoutingService, Depends(get_routing_service)],
    cursor: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=QUEUE_PAGE_SIZE)] = QUEUE_PAGE_SIZE,
) -> RoutingQueueResponse:
    tickets = manager_queue.queue(authenticated.user, RoutingRoute.RFA)
    page, next_cursor = _queue_page(tickets, cursor, limit)
    return routing_queue_response(page, routing.stats(authenticated.user), next_cursor)


@router.get("/cm/queue", response_model=RoutingQueueResponse)
async def cm_queue(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    manager_queue: Annotated[ManagerQueueService, Depends(get_manager_queue_service)],
    routing: Annotated[RoutingService, Depends(get_routing_service)],
    cursor: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=QUEUE_PAGE_SIZE)] = QUEUE_PAGE_SIZE,
) -> RoutingQueueResponse:
    tickets = manager_queue.queue(authenticated.user, RoutingRoute.CM)
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
