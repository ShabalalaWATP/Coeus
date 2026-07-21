"""Additive retrieval controlled so planner advice cannot suppress baseline evidence."""

from dataclasses import dataclass
from uuid import UUID

from coeus.domain.access import ProductStatus
from coeus.domain.auth import UserAccount
from coeus.domain.search_index import GroundedProductEvidence, GroundedSearchResult
from coeus.domain.store import StoreHybridCandidate, StoreSearchFilters
from coeus.domain.tickets import ProductOffer, TicketRecord
from coeus.services.embeddings import EmbeddingService
from coeus.services.grounded_search import GroundedSearchService
from coeus.services.rfi_grounding import merge_grounded_candidates
from coeus.services.rfi_ranking import RFI_MAX_OFFERS, query_text, rank_hybrid_rfi_candidates
from coeus.services.search_planner_agent import SearchPlan, SearchPlannerAgent
from coeus.services.search_query_controller import control_search_query
from coeus.services.store import StoreSearchService
from coeus.services.store_access import StoreDetailService

RFI_CANDIDATE_SEARCH_LIMIT = 500


@dataclass(frozen=True)
class PlannedRetrieval:
    base_query: str
    effective_query: str
    plan: SearchPlan
    baseline_candidates: tuple[StoreHybridCandidate, ...]
    supplemental_candidates: tuple[StoreHybridCandidate, ...]
    grounded: GroundedSearchResult


def retrieve_with_additive_advice(
    requester: UserAccount,
    ticket: TicketRecord,
    principal_id: UUID,
    planner: SearchPlannerAgent,
    embeddings: EmbeddingService,
    store_search: StoreSearchService,
    store_details: StoreDetailService,
    grounded_search: GroundedSearchService,
) -> PlannedRetrieval:
    """Always execute the immutable base query before any optional advice leg."""
    base_query = query_text(ticket.intake)
    baseline, base_grounded = _retrieve_leg(
        requester,
        ticket,
        principal_id,
        base_query,
        embeddings,
        store_search,
        store_details,
        grounded_search,
    )
    plan = planner.plan_safely(ticket.requester_user_id, ticket.intake)
    controlled = control_search_query(base_query, plan.suggestions)
    if not controlled.included_hints:
        return PlannedRetrieval(base_query, controlled.text, plan, baseline, (), base_grounded)
    try:
        supplemental, supplemental_grounded = _retrieve_leg(
            requester,
            ticket,
            principal_id,
            controlled.text,
            embeddings,
            store_search,
            store_details,
            grounded_search,
        )
    except Exception:
        return PlannedRetrieval(
            base_query,
            controlled.text,
            plan,
            baseline,
            (),
            _degraded_supplemental_result(base_grounded),
        )
    baseline_ids = {candidate.product.product_id for candidate in baseline}
    supplemental = tuple(
        candidate for candidate in supplemental if candidate.product.product_id not in baseline_ids
    )
    return PlannedRetrieval(
        base_query,
        controlled.text,
        plan,
        baseline,
        supplemental,
        _merge_grounded(base_grounded, supplemental_grounded),
    )


def ranked_additive_offers(
    retrieval: PlannedRetrieval, ticket: TicketRecord
) -> tuple[ProductOffer, ...]:
    """Preserve every baseline offer before appending supplemental offers."""
    baseline = rank_hybrid_rfi_candidates(retrieval.baseline_candidates, ticket.intake)
    supplemental = rank_hybrid_rfi_candidates(retrieval.supplemental_candidates, ticket.intake)
    baseline_ids = {offer.product_id for offer in baseline}
    additions = tuple(offer for offer in supplemental if offer.product_id not in baseline_ids)
    return (*baseline, *additions)[:RFI_MAX_OFFERS]


def _retrieve_leg(
    requester: UserAccount,
    ticket: TicketRecord,
    principal_id: UUID,
    query: str,
    embeddings: EmbeddingService,
    store_search: StoreSearchService,
    store_details: StoreDetailService,
    grounded_search: GroundedSearchService,
) -> tuple[tuple[StoreHybridCandidate, ...], GroundedSearchResult]:
    filters = StoreSearchFilters(
        status=ProductStatus.PUBLISHED,
        page_size=RFI_CANDIDATE_SEARCH_LIMIT,
    )
    embedding = embeddings.embed_cached(query, purpose="rfi-query", principal_id=principal_id)
    candidates = store_search.hybrid_candidates(requester, filters, query, embedding)
    grounded = grounded_search.search(requester, ticket.intake, principal_id, planned_query=query)
    return (
        merge_grounded_candidates(requester, store_details, candidates, grounded.evidence),
        grounded,
    )


def _merge_grounded(
    baseline: GroundedSearchResult, supplemental: GroundedSearchResult
) -> GroundedSearchResult:
    evidence = _union_evidence(baseline.evidence, supplemental.evidence)
    releases_match = (
        baseline.profile_space_id == supplemental.profile_space_id
        and baseline.corpus_version == supplemental.corpus_version
    )
    complete = (
        baseline.coverage_status == supplemental.coverage_status == "complete" and releases_match
    )
    return GroundedSearchResult(
        evidence=evidence,
        retrieval_mode=baseline.retrieval_mode,
        degraded_reason=(
            None
            if complete
            else baseline.degraded_reason
            or supplemental.degraded_reason
            or "supplemental_search_incomplete"
        ),
        profile_space_id=baseline.profile_space_id if complete else None,
        coverage_status="complete" if complete else "partial",
        corpus_version=baseline.corpus_version if releases_match else None,
    )


def _degraded_supplemental_result(baseline: GroundedSearchResult) -> GroundedSearchResult:
    """Retain authorised baseline evidence without claiming complete planner coverage."""
    return GroundedSearchResult(
        evidence=baseline.evidence,
        retrieval_mode=baseline.retrieval_mode,
        degraded_reason="supplemental_search_failed",
        profile_space_id=baseline.profile_space_id,
        coverage_status="partial",
        corpus_version=baseline.corpus_version,
    )


def _union_evidence(
    baseline: tuple[GroundedProductEvidence, ...],
    supplemental: tuple[GroundedProductEvidence, ...],
) -> tuple[GroundedProductEvidence, ...]:
    result = list(baseline)
    seen = {item.product_id for item in baseline}
    result.extend(item for item in supplemental if item.product_id not in seen)
    return tuple(result)
