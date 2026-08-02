from collections import Counter
from collections.abc import Iterable
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
    StoreFacetValue,
    StoreHybridCandidate,
    StoreProduct,
    StoreSearchFilters,
    StoreSearchHit,
    StoreSearchResult,
    StoreSortOrder,
)
from coeus.domain.store_ranking import tokenize
from coeus.services.store_semantics import product_semantic_text, semantic_label_reasons

STORE_LEXICAL_SCORE_FLOOR = 1e-12


def has_text_query(filters: StoreSearchFilters) -> bool:
    return filters.query is not None and filters.query.strip() != ""


def without_text_query(filters: StoreSearchFilters) -> StoreSearchFilters:
    return replace(filters, query=None)


def relaxed_query(query: str) -> str | None:
    """Return an any-term form of a multi-term query, or None if pointless.

    PostgreSQL's ``websearch_to_tsquery`` requires every term, so a natural
    phrase such as "arctic shipping routes" returns nothing even when strong
    partial matches exist. Joining the terms with OR lets the lexical leg offer
    those matches; the caller flags the result as broadened so the operator is
    never shown partial matches as if they were exact.
    """
    tokens = tokenize(query)
    if len(tokens) < 2:
        return None
    return " OR ".join(tokens)


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
    relaxed: bool = False,
) -> StoreSearchResult:
    ordered = sort_hits(hits, filters.sort)
    offset = (filters.page - 1) * filters.page_size
    page_hits = ordered[offset : offset + filters.page_size]
    return StoreSearchResult(
        hits=page_hits,
        total=len(ordered),
        page=filters.page,
        page_size=filters.page_size,
        total_pages=ceil(len(ordered) / filters.page_size) if ordered else 0,
        facets=facets,
        relaxed=relaxed,
    )


def projected_page_result(
    products: tuple[StoreProduct, ...],
    total: int,
    filters: StoreSearchFilters,
    facets: StoreFacets,
) -> StoreSearchResult:
    return StoreSearchResult(
        hits=tuple(exact_text_hit(product) for product in products),
        total=total,
        page=filters.page,
        page_size=filters.page_size,
        total_pages=ceil(total / filters.page_size) if total else 0,
        facets=facets,
    )


def facets_for(products: tuple[StoreProduct, ...]) -> StoreFacets:
    return StoreFacets(
        product_types=_counted(product.metadata.product_type for product in products),
        regions=_counted(product.metadata.area_or_region for product in products),
        tags=_counted(tag for product in products for tag in product.metadata.tags),
    )


def sort_hits_by_relevance(hits: tuple[StoreSearchHit, ...]) -> tuple[StoreSearchHit, ...]:
    return tuple(sorted(hits, key=lambda hit: (-hit.match_score, hit.product.metadata.title)))


def sort_hits(
    hits: tuple[StoreSearchHit, ...],
    sort: StoreSortOrder,
) -> tuple[StoreSearchHit, ...]:
    """Order every matching hit before paging, so sort holds across pages."""
    if sort is StoreSortOrder.TITLE:
        return tuple(sorted(hits, key=_title_key))
    if sort is StoreSortOrder.COVERAGE:
        # Sorting by title first and coverage second gives titles as the tie
        # break, because Python's sort is stable and keeps equal elements in
        # their existing order even when reversed. An absent coverage window
        # becomes the lowest key, so undated products sort last.
        by_title = sorted(hits, key=_title_key)
        return tuple(
            sorted(
                by_title,
                key=lambda hit: hit.product.metadata.time_period_start or "",
                reverse=True,
            )
        )
    return sort_hits_by_relevance(hits)


def _title_key(hit: StoreSearchHit) -> str:
    return hit.product.metadata.title.casefold()


def _counted(values: Iterable[str]) -> tuple[StoreFacetValue, ...]:
    counts = Counter(values)
    return tuple(StoreFacetValue(value=value, count=counts[value]) for value in sorted(counts))


def _hybrid_hit(
    candidate: StoreHybridCandidate,
    query: str,
    available_legs: int,
) -> StoreSearchHit:
    reasons = _hybrid_reasons(candidate, query)
    rrf = hybrid_rrf_score(
        candidate,
        available_legs,
        lexical_floor=STORE_LEXICAL_SCORE_FLOOR,
        vector_floor=VECTOR_SIMILARITY_FLOOR,
    )
    vector_signal = max(
        0.0,
        (candidate.vector_score - VECTOR_SIMILARITY_FLOOR) / (1.0 - VECTOR_SIMILARITY_FLOOR),
    )
    return StoreSearchHit(
        product=candidate.product,
        match_score=round(
            min(1.0, (0.65 * candidate.lexical_score) + (0.30 * vector_signal) + (0.05 * rrf)),
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
