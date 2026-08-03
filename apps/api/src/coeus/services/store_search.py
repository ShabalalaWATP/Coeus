"""Authorised, bounded Intelligence Store search orchestration."""

from dataclasses import replace

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.store import (
    StoreFacets,
    StoreHybridCandidate,
    StoreProduct,
    StoreProductSearchPage,
    StoreSearchFilters,
    StoreSearchHit,
    StoreSearchResult,
    StoreVisibilityScope,
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
    relaxed_query,
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
        scope = self._visibility_scope(actor, filters)
        structured_filters = without_text_query(filters)
        projected_page = self._repository.search_product_page(structured_filters, scope)
        filtered = (
            self._local_filtered_products(actor, structured_filters)
            if projected_page is None
            else ()
        )
        # Facet values and counts are derived in SQL. If any product the same
        # projection returned fails the in-process policy recheck, the SQL scope
        # has drifted from the API rules, so nothing derived from that
        # projection may be reported on either path.
        projection_trusted = projected_page is None or self._page_is_authorised(
            actor, projected_page, structured_filters
        )
        if projected_page is None:
            facets = facets_for(filtered)
        else:
            facets = projected_page.facets if projection_trusted else StoreFacets((), (), ())
        if has_text_query(filters):
            query = filters.query.strip() if filters.query else ""
            query_embedding = (
                self._embeddings.embed_cached(
                    query, purpose="store-browse-query", principal_id=actor.user_id
                )
                if self._embeddings is not None
                else None
            )
            hits = self._text_hits(actor, filters, query, query, query_embedding)
            if hits:
                return paged_result(hits, filters, facets)
            broadened = relaxed_query(query)
            if broadened is None:
                return paged_result((), filters, facets)
            hits = self._text_hits(actor, filters, broadened, query, query_embedding)
            return paged_result(hits, filters, facets, relaxed=bool(hits))
        if projected_page is not None:
            if not projection_trusted:
                return projected_page_result((), 0, filters, StoreFacets((), (), ()))
            return projected_page_result(
                projected_page.products,
                projected_page.total,
                filters,
                facets,
            )
        # paged_result orders every hit for the requested sort before paging.
        return paged_result(tuple(exact_text_hit(product) for product in filtered), filters, facets)

    def _page_is_authorised(
        self,
        actor: UserAccount,
        page: StoreProductSearchPage,
        structured_filters: StoreSearchFilters,
    ) -> bool:
        """Recheck the SQL projection against the API access rules."""
        return all(
            self._policy.can_read(actor, product)
            and structured_filter_match(product, structured_filters)
            for product in page.products
        )

    def _text_hits(
        self,
        actor: UserAccount,
        filters: StoreSearchFilters,
        retrieval_query: str,
        reason_query: str,
        query_embedding: tuple[float, ...] | None,
    ) -> tuple[StoreSearchHit, ...]:
        """Retrieve with one query form but explain the match with the user's own.

        A broadened retry must not report the OR-joined terms it searched with,
        so match reasons are always derived from what the operator typed.
        """
        return hybrid_hits(
            self.hybrid_candidates(
                actor,
                filters,
                retrieval_query,
                query_embedding,
                leg_limit=STORE_BROWSE_HYBRID_LEG_LIMIT,
            ),
            reason_query,
        )

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
            self._visibility_scope(actor, filters),
            query,
            query_embedding,
            leg_limit,
        )
        return tuple(
            candidate for candidate in candidates if self._policy.can_read(actor, candidate.product)
        )

    def _visibility_scope(
        self, actor: UserAccount, filters: StoreSearchFilters
    ) -> StoreVisibilityScope:
        scope = self._policy.visibility_scope(actor)
        if filters.acg_ids:
            if not filters.acg_ids.issubset(scope.acg_ids):
                raise AppError(404, "acg_not_found", "Access control group was not found.")
            return replace(scope, acg_ids=filters.acg_ids)
        return scope


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
    return bool(filters.acg_ids) or any(value not in (None, "") for value in criteria)
