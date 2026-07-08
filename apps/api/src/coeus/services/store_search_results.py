from dataclasses import replace
from math import ceil

from coeus.domain.store import (
    StoreFacets,
    StoreHybridCandidate,
    StoreProduct,
    StoreSearchFilters,
    StoreSearchHit,
    StoreSearchResult,
)
from coeus.services.rfi_ranking import (
    LEXICAL_SCORE_FLOOR,
    RRF_K,
    VECTOR_SIMILARITY_FLOOR,
    tokenize,
)
from coeus.services.store_search_dates import within_dates
from coeus.services.store_semantics import product_semantic_text, semantic_label_reasons


def has_text_query(filters: StoreSearchFilters) -> bool:
    return filters.query is not None and filters.query.strip() != ""


def without_text_query(filters: StoreSearchFilters) -> StoreSearchFilters:
    return replace(filters, query=None)


def structured_filter_match(product: StoreProduct, filters: StoreSearchFilters) -> bool:
    metadata = product.metadata
    return all(
        (
            filters.product_type is None or metadata.product_type == filters.product_type,
            _contains(metadata.area_or_region, filters.region),
            filters.tag is None
            or filters.tag.casefold() in {tag.casefold() for tag in metadata.tags},
            filters.source_type is None or metadata.source_type == filters.source_type,
            filters.status is None or metadata.status == filters.status,
            filters.project_id is None or metadata.project_id == filters.project_id,
            within_dates(metadata, filters.date_from, filters.date_to),
            filters.owner_team is None
            or metadata.owner_team.casefold() == filters.owner_team.casefold(),
        )
    )


def exact_text_hit(product: StoreProduct, query: str | None) -> StoreSearchHit:
    if query is None or query.strip() == "":
        return StoreSearchHit(product=product, match_score=1.0, match_reasons=("visible",))
    query_tokens = tokenize(query)
    document_tokens = set(tokenize(product_semantic_text(product)))
    matches = tuple(token for token in query_tokens if token in document_tokens)
    score = len(matches) / max(len(query_tokens), 1)
    return StoreSearchHit(
        product=product,
        match_score=score,
        match_reasons=tuple(f"full-text:{token}" for token in matches) or ("visible",),
    )


def hybrid_hits(
    candidates: tuple[StoreHybridCandidate, ...],
    query: str,
) -> tuple[StoreSearchHit, ...]:
    available_legs = _available_legs(candidates)
    hits = tuple(_hybrid_hit(candidate, query, available_legs) for candidate in candidates)
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
        match_score=round(_rrf_score(candidate, available_legs), 4),
        match_reasons=tuple(dict.fromkeys(reasons)) or ("visible",),
    )


def _hybrid_reasons(candidate: StoreHybridCandidate, query: str) -> tuple[str, ...]:
    reasons: list[str] = []
    if candidate.lexical_rank is not None and candidate.lexical_score >= LEXICAL_SCORE_FLOOR:
        reasons.append(f"lexical-rank:{candidate.lexical_rank}")
    if candidate.vector_rank is not None and candidate.vector_score >= VECTOR_SIMILARITY_FLOOR:
        reasons.append(f"vector-similarity:{candidate.vector_score:.2f}")
    if candidate.lexical_only:
        reasons.append("retrieval:lexical-only")
    reasons.extend(semantic_label_reasons(candidate.product, query))
    reasons.extend(_matched_text_reasons(candidate.product, query)[:3])
    return tuple(reasons)


def _matched_text_reasons(product: StoreProduct, query: str) -> tuple[str, ...]:
    document_tokens = set(tokenize(product_semantic_text(product)))
    return tuple(f"full-text:{token}" for token in tokenize(query) if token in document_tokens)


def _available_legs(candidates: tuple[StoreHybridCandidate, ...]) -> int:
    lexical = any(
        candidate.lexical_rank is not None and candidate.lexical_score >= LEXICAL_SCORE_FLOOR
        for candidate in candidates
    )
    vector = any(
        candidate.vector_rank is not None and candidate.vector_score >= VECTOR_SIMILARITY_FLOOR
        for candidate in candidates
    )
    return max(1, int(lexical) + int(vector))


def _rrf_score(candidate: StoreHybridCandidate, available_legs: int) -> float:
    raw = 0.0
    if candidate.lexical_rank is not None and candidate.lexical_score >= LEXICAL_SCORE_FLOOR:
        raw += 1 / (RRF_K + candidate.lexical_rank)
    if candidate.vector_rank is not None and candidate.vector_score >= VECTOR_SIMILARITY_FLOOR:
        raw += 1 / (RRF_K + candidate.vector_rank)
    max_possible = available_legs / (RRF_K + 1)
    return raw / max_possible if max_possible else 0.0


def _contains(value: str, needle: str | None) -> bool:
    return needle is None or needle.casefold() in value.casefold()
