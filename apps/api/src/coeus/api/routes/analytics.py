from typing import Annotated

from fastapi import APIRouter, Depends

from coeus.api.dependencies import (
    get_admin_analytics_service,
    get_current_session,
    get_feedback_analytics_service,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.schemas.admin_analytics import AdminAnalyticsDashboardResponse
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
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    service: Annotated[AdminAnalyticsService, Depends(get_admin_analytics_service)],
) -> AdminAnalyticsDashboardResponse:
    return AdminAnalyticsDashboardResponse.model_validate(service.dashboard(authenticated.user))


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
