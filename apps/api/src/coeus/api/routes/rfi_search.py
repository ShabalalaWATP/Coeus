from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from coeus.api.dependencies import (
    get_csrf_validated_session,
    get_current_session,
    get_rfi_search_service,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.tickets import ProductOffer, RfiSearchMetrics
from coeus.schemas.rfi_search import (
    RejectProductOfferRequest,
    RfiProductOfferResponse,
    RfiSearchMetricsResponse,
    RfiSearchResultsResponse,
)
from coeus.services.rfi_search import RfiSearchResults, RfiSearchService

router = APIRouter(prefix="/rfi-search", tags=["rfi-search"])


@router.post("/{ticket_id}/run", response_model=RfiSearchResultsResponse)
async def run_rfi_search(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    rfi_search: Annotated[RfiSearchService, Depends(get_rfi_search_service)],
) -> RfiSearchResultsResponse:
    return _to_response(rfi_search.run(authenticated.user, ticket_id))


@router.get("/{ticket_id}/results", response_model=RfiSearchResultsResponse)
async def get_rfi_search_results(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    rfi_search: Annotated[RfiSearchService, Depends(get_rfi_search_service)],
) -> RfiSearchResultsResponse:
    return _to_response(rfi_search.results(authenticated.user, ticket_id))


@router.post("/{ticket_id}/offers/{product_id}/accept", response_model=RfiSearchResultsResponse)
async def accept_product_offer(
    ticket_id: UUID,
    product_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    rfi_search: Annotated[RfiSearchService, Depends(get_rfi_search_service)],
) -> RfiSearchResultsResponse:
    return _to_response(rfi_search.accept(authenticated.user, ticket_id, product_id))


@router.post("/{ticket_id}/offers/{product_id}/reject", response_model=RfiSearchResultsResponse)
async def reject_product_offer(
    ticket_id: UUID,
    product_id: UUID,
    payload: RejectProductOfferRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    rfi_search: Annotated[RfiSearchService, Depends(get_rfi_search_service)],
) -> RfiSearchResultsResponse:
    return _to_response(
        rfi_search.reject(authenticated.user, ticket_id, product_id, payload.reason)
    )


def _to_response(result: RfiSearchResults) -> RfiSearchResultsResponse:
    return RfiSearchResultsResponse(
        ticket_id=result.ticket.ticket_id,
        ticket_state=result.ticket.state.value,
        offers=[_offer_response(offer) for offer in result.offers],
        metrics=_metrics_response(result.metrics) if result.metrics is not None else None,
    )


def _offer_response(offer: ProductOffer) -> RfiProductOfferResponse:
    return RfiProductOfferResponse(
        product_id=offer.product_id,
        title=offer.title,
        summary=offer.summary,
        product_type=offer.product_type,
        match_score=offer.match_score,
        match_reasons=list(offer.match_reasons),
        classification_level=offer.classification_level,
        releasability=list(offer.releasability),
        region=offer.region,
        time_period_start=offer.time_period_start,
        time_period_end=offer.time_period_end,
        asset_types=list(offer.asset_types),
        offerable_to_user=offer.offerable_to_user,
        status=offer.status.value,
        rejection_reason=offer.rejection_reason,
    )


def _metrics_response(metrics: RfiSearchMetrics) -> RfiSearchMetricsResponse:
    return RfiSearchMetricsResponse(
        run_id=metrics.run_id,
        query=metrics.query,
        candidate_count=metrics.candidate_count,
        offered_count=metrics.offered_count,
        rejected_count=metrics.rejected_count,
        accepted_product_id=metrics.accepted_product_id,
        created_at=metrics.created_at,
    )
