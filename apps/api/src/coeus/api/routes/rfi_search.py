from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from coeus.api.dependencies import (
    get_csrf_validated_session,
    get_current_session,
    get_rfi_search_service,
    get_search_admission,
    get_settings,
)
from coeus.api.workflow_dependencies import get_active_work_discovery_service
from coeus.application.ports.admission import ResourceAdmission
from coeus.core.async_work import run_bounded_search
from coeus.core.config import Settings
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.enums import TicketState
from coeus.domain.search_metrics import RfiSearchMetrics
from coeus.domain.tickets import ProductOffer
from coeus.schemas.rfi_search import (
    RejectProductOfferRequest,
    RfiEvidencePassageResponse,
    RfiProductOfferResponse,
    RfiSearchMetricsResponse,
    RfiSearchResultsResponse,
)
from coeus.services.active_work_discovery import ActiveWorkDiscoveryService
from coeus.services.rfi_search import RfiSearchService
from coeus.services.rfi_search_types import RfiSearchResults

router = APIRouter(prefix="/rfi-search", tags=["rfi-search"])


@router.post("/{ticket_id}/run", response_model=RfiSearchResultsResponse)
async def run_rfi_search(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    rfi_search: Annotated[RfiSearchService, Depends(get_rfi_search_service)],
    admission: Annotated[ResourceAdmission, Depends(get_search_admission)],
    active_work: Annotated[ActiveWorkDiscoveryService, Depends(get_active_work_discovery_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RfiSearchResultsResponse:
    with admission.reserve(authenticated.user.user_id):
        result = await run_bounded_search(rfi_search.run, authenticated.user, ticket_id)
    if (
        result.ticket.state == TicketState.NEW_TASKING_CONSENT
        and settings.active_work_offers_enabled
    ):
        active_work.discover(authenticated.user, ticket_id)
        result = rfi_search.results(authenticated.user, ticket_id)
    return _to_response(result)


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
    active_work: Annotated[ActiveWorkDiscoveryService, Depends(get_active_work_discovery_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RfiSearchResultsResponse:
    result = rfi_search.reject(authenticated.user, ticket_id, product_id, payload.reason)
    if (
        result.ticket.state == TicketState.NEW_TASKING_CONSENT
        and settings.active_work_offers_enabled
    ):
        active_work.discover(authenticated.user, ticket_id)
        result = rfi_search.results(authenticated.user, ticket_id)
    return _to_response(result)


def _to_response(result: RfiSearchResults) -> RfiSearchResultsResponse:
    return RfiSearchResultsResponse(
        ticket_id=result.ticket.ticket_id,
        ticket_state=result.ticket.state.value,
        offers=[_offer_response(offer, result) for offer in result.offers],
        metrics=_metrics_response(result.metrics) if result.metrics is not None else None,
        retrieval_mode=result.retrieval_mode,
        degraded_reason=result.degraded_reason,
        outcome=result.outcome,
        assurance=result.assurance,
    )


def _offer_response(offer: ProductOffer, result: RfiSearchResults) -> RfiProductOfferResponse:
    evidence = next((item for item in result.evidence if item.product_id == offer.product_id), None)
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
        passages=[
            RfiEvidencePassageResponse(
                citation=(
                    passage.asset_name
                    if passage.page_number == 0
                    else f"{passage.asset_name}, page {passage.page_number}"
                ),
                chunk_id=passage.chunk_id,
                asset_id=passage.asset_id,
                asset_name=passage.asset_name,
                page_number=passage.page_number,
                excerpt=passage.excerpt,
            )
            for passage in evidence.passages
        ]
        if evidence
        else [],
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
        retrieval_mode=metrics.retrieval_mode,
        degraded_reason=metrics.degraded_reason,
        outcome=metrics.outcome,
        assurance=metrics.assurance,
        coverage_status=metrics.coverage_status,
        profile_space_id=metrics.profile_space_id,
        corpus_version=metrics.corpus_version,
    )
