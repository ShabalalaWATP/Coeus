import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from coeus.api.dependencies import (
    get_admin_analytics_service,
    get_csrf_validated_session,
    get_current_session,
    get_feedback_analytics_service,
    require_permission,
)
from coeus.application.ports.outbox import OutboxDispatcherPort
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import AuthenticatedSession
from coeus.schemas.admin_analytics import (
    AdminAnalyticsDashboardResponse,
    OutboxReplayRequest,
    OutboxReplayResponse,
)
from coeus.schemas.feedback_analytics import (
    AnalyticsDashboardResponse,
    AnalyticsMetricsResponse,
    ProductReuseResponse,
    TrendInsightResponse,
)
from coeus.services.admin_analytics import AdminAnalyticsService
from coeus.services.feedback_analytics import (
    AnalyticsAudience,
    AnalyticsDashboard,
    FeedbackAnalyticsService,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/admin/platform", response_model=AdminAnalyticsDashboardResponse)
async def admin_platform_dashboard(
    request: Request,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    service: Annotated[AdminAnalyticsService, Depends(get_admin_analytics_service)],
) -> AdminAnalyticsDashboardResponse:
    dashboard = await asyncio.to_thread(
        service.dashboard,
        authenticated.user,
        _outbox_dispatcher(request, required=False),
    )
    return AdminAnalyticsDashboardResponse.model_validate(dashboard)


@router.post(
    "/admin/outbox/{event_id}/replay",
    response_model=OutboxReplayResponse,
)
async def replay_dead_letter(
    event_id: UUID,
    payload: OutboxReplayRequest,
    request: Request,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    permitted: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.SYSTEM_CONFIGURE)),
    ],
    service: Annotated[AdminAnalyticsService, Depends(get_admin_analytics_service)],
) -> OutboxReplayResponse:
    del permitted
    outbox = _outbox_dispatcher(request, required=True)
    if outbox is None:  # pragma: no cover - required=True raises first
        raise AppError(503, "outbox_not_configured", "Outbox delivery is not configured.")
    disposition = await asyncio.to_thread(
        service.replay_dead_letter,
        authenticated.user,
        outbox,
        event_id,
        payload.reason,
    )
    return OutboxReplayResponse(event_id=event_id, disposition=disposition.value)


@router.get("/admin", response_model=AnalyticsDashboardResponse, deprecated=True)
async def admin_dashboard(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    service: Annotated[AdminAnalyticsService, Depends(get_admin_analytics_service)],
) -> AnalyticsDashboardResponse:
    """Retain the old shape without returning intelligence workflow detail."""
    service.dashboard(authenticated.user)
    return AnalyticsDashboardResponse(
        audience="admin",
        metrics=AnalyticsMetricsResponse(
            total_tickets=0,
            active_tickets=0,
            disseminations=0,
            feedback_requested=0,
            feedback_submitted=0,
            average_rating=None,
            average_search_candidates=None,
            rfa_routes=0,
            collection_routes=0,
        ),
        product_reuse=[],
        trends=[],
    )


@router.get("/rfa", response_model=AnalyticsDashboardResponse)
async def rfa_dashboard(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    service: Annotated[FeedbackAnalyticsService, Depends(get_feedback_analytics_service)],
) -> AnalyticsDashboardResponse:
    return _dashboard_response(service.dashboard(authenticated.user, AnalyticsAudience.RFA))


@router.get("/collection", response_model=AnalyticsDashboardResponse)
async def collection_dashboard(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    service: Annotated[FeedbackAnalyticsService, Depends(get_feedback_analytics_service)],
) -> AnalyticsDashboardResponse:
    return _dashboard_response(service.dashboard(authenticated.user, AnalyticsAudience.COLLECTION))


def _dashboard_response(dashboard: AnalyticsDashboard) -> AnalyticsDashboardResponse:
    metrics = dashboard.metrics
    return AnalyticsDashboardResponse(
        audience=dashboard.audience.value,
        metrics=AnalyticsMetricsResponse(
            total_tickets=metrics.total_tickets,
            active_tickets=metrics.active_tickets,
            disseminations=metrics.disseminations,
            feedback_requested=metrics.feedback_requested,
            feedback_submitted=metrics.feedback_submitted,
            average_rating=metrics.average_rating,
            average_search_candidates=metrics.average_search_candidates,
            rfa_routes=metrics.rfa_routes,
            collection_routes=metrics.collection_routes,
        ),
        product_reuse=[
            ProductReuseResponse(
                product_id=item.product_id,
                reference=item.reference,
                title=item.title,
                owner_team=item.owner_team,
                dissemination_count=item.dissemination_count,
                accepted_offer_count=item.accepted_offer_count,
                feedback_count=item.feedback_count,
                average_rating=item.average_rating,
            )
            for item in dashboard.product_reuse
        ],
        trends=[
            TrendInsightResponse(
                title=item.title,
                summary=item.summary,
                signal=item.signal,
                confidence=item.confidence,
            )
            for item in dashboard.trends
        ],
    )


def _outbox_dispatcher(request: Request, *, required: bool) -> OutboxDispatcherPort | None:
    dispatcher: OutboxDispatcherPort | None = getattr(request.app.state, "outbox_dispatcher", None)
    if dispatcher is None and required:
        raise AppError(503, "outbox_not_configured", "Outbox delivery is not configured.")
    return dispatcher
