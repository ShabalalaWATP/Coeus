"""Authorised, bounded Intelligence Store search orchestration."""

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.store import (
    StoreFacets,
    StoreHybridCandidate,
    StoreProduct,
    StoreSearchFilters,
    StoreSearchResult,
)
from coeus.domain.store_filters import structured_filter_match
from coeus.repositories.store import StoreRepository
from coeus.services.embeddings import EmbeddingService
from coeus.services.store_pagination import require_bounded_result_window
from coeus.services.store_product_policy import StoreProductAccessPolicy
from coeus.services.store_search_results import (
    exact_text_hit,
    facets_for,
    has_text_query,
    hybrid_hits,
    paged_result,
    projected_page_result,
    sort_hits_by_relevance,
    without_text_query,
)

STORE_BROWSE_HYBRID_LEG_LIMIT = 500


class StoreSearchService:
    def __init__(
        self,
        repository: StoreRepository,
        policy: StoreProductAccessPolicy,
        embeddings: EmbeddingService | None = None,
    ) -> None:
        self._repository = repository
        self._policy = policy
        self._embeddings = embeddings

    def search(self, actor: UserAccount, filters: StoreSearchFilters) -> StoreSearchResult:
        if Permission.PRODUCT_SEARCH not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
        if not _has_search_criteria(filters) and (
            Permission.STORE_BROWSE_ALL not in actor.permissions
        ):
            raise AppError(
                422,
                "search_criteria_required",
                "Enter a search term or filter to view store products.",
            )
        require_bounded_result_window(filters)
        scope = self._policy.visibility_scope(actor)
        structured_filters = without_text_query(filters)
        projected_page = self._repository.search_product_page(structured_filters, scope)
        filtered = (
            self._local_filtered_products(actor, structured_filters)
            if projected_page is None
            else ()
        )
        facets = facets_for(filtered) if projected_page is None else projected_page.facets
        if has_text_query(filters):
            query = filters.query.strip() if filters.query else ""
            query_embedding = (
                self._embeddings.embed_cached(
                    query, purpose="store-browse-query", principal_id=actor.user_id
                )
                if self._embeddings is not None
                else None
            )
            hits = hybrid_hits(
                self.hybrid_candidates(
                    actor,
                    filters,
                    query,
                    query_embedding,
                    leg_limit=STORE_BROWSE_HYBRID_LEG_LIMIT,
                ),
                query,
            )
            return paged_result(hits, filters, facets)
        if projected_page is not None:
            visible_page = tuple(
                product
                for product in projected_page.products
                if self._policy.can_read(actor, product)
                and structured_filter_match(product, structured_filters)
            )
            if len(visible_page) != len(projected_page.products):
                return projected_page_result((), 0, filters, StoreFacets((), (), ()))
            return projected_page_result(
                visible_page,
                projected_page.total,
                filters,
                projected_page.facets,
            )
        hits = sort_hits_by_relevance(tuple(exact_text_hit(product) for product in filtered))
        return paged_result(hits, filters, facets)

    def _local_filtered_products(
        self,
        actor: UserAccount,
        filters: StoreSearchFilters,
    ) -> tuple[StoreProduct, ...]:
        return tuple(
            product
            for product in self._repository.list_products()
            if self._policy.can_read(actor, product) and structured_filter_match(product, filters)
        )

    def hybrid_candidates(
        self,
        actor: UserAccount,
        filters: StoreSearchFilters,
        query: str,
        query_embedding: tuple[float, ...] | None,
        leg_limit: int = 50,
    ) -> tuple[StoreHybridCandidate, ...]:
        if Permission.PRODUCT_SEARCH not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
        candidates = self._repository.hybrid_candidates(
            filters,
            self._policy.visibility_scope(actor),
            query,
            query_embedding,
            leg_limit,
        )
        return tuple(
            candidate for candidate in candidates if self._policy.can_read(actor, candidate.product)
        )


def _has_search_criteria(filters: StoreSearchFilters) -> bool:
    """At least one purposeful criterion beyond pagination."""
    criteria = (
        filters.query,
        filters.product_type,
        filters.region,
        filters.tag,
        filters.source_type,
        filters.status,
        filters.date_from,
        filters.date_to,
        filters.owner_team,
    )
    return any(value not in (None, "") for value in criteria)
