from dataclasses import replace
from math import ceil

from coeus.domain.search_relevance import (
    VECTOR_SIMILARITY_FLOOR,
    available_hybrid_legs,
    hybrid_rrf_score,
    matched_tokens,
)
from coeus.domain.store import (
    StoreFacets,
    StoreHybridCandidate,
    StoreProduct,
    StoreSearchFilters,
    StoreSearchHit,
    StoreSearchResult,
)
from coeus.services.rfi_ranking import tokenize
from coeus.services.store_semantics import product_semantic_text, semantic_label_reasons

STORE_LEXICAL_SCORE_FLOOR = 1e-12


def has_text_query(filters: StoreSearchFilters) -> bool:
    return filters.query is not None and filters.query.strip() != ""


def without_text_query(filters: StoreSearchFilters) -> StoreSearchFilters:
    return replace(filters, query=None)


def exact_text_hit(product: StoreProduct) -> StoreSearchHit:
    return StoreSearchHit(product=product, match_score=1.0, match_reasons=("visible",))


def hybrid_hits(
    candidates: tuple[StoreHybridCandidate, ...],
    query: str,
) -> tuple[StoreSearchHit, ...]:
    eligible = tuple(candidate for candidate in candidates if _has_query_signal(candidate))
    available_legs = available_hybrid_legs(
        eligible,
        lexical_floor=STORE_LEXICAL_SCORE_FLOOR,
        vector_floor=VECTOR_SIMILARITY_FLOOR,
    )
    hits = tuple(_hybrid_hit(candidate, query, available_legs) for candidate in eligible)
    return tuple(sorted(hits, key=lambda hit: (-hit.match_score, hit.product.metadata.title)))


def paged_result(
    hits: tuple[StoreSearchHit, ...],
    filters: StoreSearchFilters,
    facets: StoreFacets,
) -> StoreSearchResult:
    offset = (filters.page - 1) * filters.page_size
    page_hits = hits[offset : offset + filters.page_size]
    return StoreSearchResult(
        hits=page_hits,
        total=len(hits),
        page=filters.page,
        page_size=filters.page_size,
        total_pages=ceil(len(hits) / filters.page_size) if hits else 0,
        facets=facets,
    )


def facets_for(products: tuple[StoreProduct, ...]) -> StoreFacets:
    return StoreFacets(
        product_types=tuple(sorted({product.metadata.product_type for product in products})),
        regions=tuple(sorted({product.metadata.area_or_region for product in products})),
        tags=tuple(sorted({tag for product in products for tag in product.metadata.tags})),
    )


def sort_hits_by_relevance(hits: tuple[StoreSearchHit, ...]) -> tuple[StoreSearchHit, ...]:
    return tuple(sorted(hits, key=lambda hit: (-hit.match_score, hit.product.metadata.title)))


def _hybrid_hit(
    candidate: StoreHybridCandidate,
    query: str,
    available_legs: int,
) -> StoreSearchHit:
    reasons = _hybrid_reasons(candidate, query)
    return StoreSearchHit(
        product=candidate.product,
        match_score=round(
            hybrid_rrf_score(
                candidate,
                available_legs,
                lexical_floor=STORE_LEXICAL_SCORE_FLOOR,
                vector_floor=VECTOR_SIMILARITY_FLOOR,
            ),
            4,
        ),
        match_reasons=tuple(dict.fromkeys(reasons)),
    )


def _hybrid_reasons(candidate: StoreHybridCandidate, query: str) -> tuple[str, ...]:
    reasons: list[str] = []
    if _has_lexical_signal(candidate):
        reasons.append(f"lexical-rank:{candidate.lexical_rank}")
    if _has_vector_signal(candidate):
        reasons.append(f"vector-similarity:{candidate.vector_score:.2f}")
    if candidate.lexical_only:
        reasons.append("retrieval:lexical-only")
    reasons.extend(semantic_label_reasons(candidate.product, query))
    reasons.extend(_matched_text_reasons(candidate.product, query)[:3])
    return tuple(reasons)


def _matched_text_reasons(product: StoreProduct, query: str) -> tuple[str, ...]:
    return tuple(
        f"full-text:{token}"
        for token in matched_tokens(tokenize(query), tokenize(product_semantic_text(product)))
    )


def _has_query_signal(candidate: StoreHybridCandidate) -> bool:
    return _has_lexical_signal(candidate) or _has_vector_signal(candidate)


def _has_lexical_signal(candidate: StoreHybridCandidate) -> bool:
    return (
        candidate.lexical_rank is not None and candidate.lexical_score >= STORE_LEXICAL_SCORE_FLOOR
    )


def _has_vector_signal(candidate: StoreHybridCandidate) -> bool:
    return candidate.vector_rank is not None and candidate.vector_score >= VECTOR_SIMILARITY_FLOOR
