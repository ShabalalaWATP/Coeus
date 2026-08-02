"""A natural multi-term phrase must not dead-end when close matches exist.

PostgreSQL's ``websearch_to_tsquery`` requires every term, so "arctic shipping
routes" retrieves nothing even when strongly related products are held. The
service retries once with an any-term query and reports that it broadened the
search, so partial matches are never presented as exact ones.
"""

from dataclasses import replace
from uuid import uuid4

from coeus.domain.store import (
    StoreHybridCandidate,
    StoreProduct,
    StoreSearchFilters,
)
from coeus.domain.store_ranking import tokenize
from coeus.repositories.store import InMemoryStoreRepository
from coeus.services.store import StoreSearchService
from coeus.services.store_product_policy import StoreProductAccessPolicy
from store_projection_helpers import RecordingProjection, access_repository, seed_product


class AndSemanticsProjection(RecordingProjection):
    """Mimic the lexical leg: every term must be present unless OR-joined."""

    def __init__(self, products: tuple[StoreProduct, ...]) -> None:
        super().__init__(products)
        self.retrieval_queries: list[str] = []

    def hybrid_candidates(
        self,
        _filters: object,
        _scope: object,
        _query: str,
        _query_embedding: tuple[float, ...] | None,
        _leg_limit: int = 50,
    ) -> tuple[StoreHybridCandidate, ...]:
        self.retrieval_queries.append(_query)
        any_term = " OR " in _query
        terms = [term for term in tokenize(_query) if term != "or"]
        matched = [
            product for product in self.products if _matches(product, terms, any_term=any_term)
        ]
        return tuple(
            StoreHybridCandidate(product=product, lexical_rank=index + 1, lexical_score=0.6)
            for index, product in enumerate(matched)
        )


def _matches(product: StoreProduct, terms: list[str], *, any_term: bool) -> bool:
    title_tokens = set(tokenize(product.metadata.title))
    present = [term for term in terms if term in title_tokens]
    return bool(present) if any_term else len(present) == len(terms)


def _catalogue() -> tuple[StoreProduct, ...]:
    base = seed_product()
    titles = ("Arctic Route Intelligence Bundle", "Baltic Shipping Watch")
    return tuple(
        replace(
            base,
            product_id=uuid4(),
            reference=f"PROD-REL-{index}",
            metadata=replace(base.metadata, title=title),
        )
        for index, title in enumerate(titles)
    )


def _service(projection: RecordingProjection) -> tuple[StoreSearchService, object]:
    access = access_repository()
    admin = access.get_user_by_username("admin@example.test")
    assert admin is not None
    repository = InMemoryStoreRepository(access, projection=projection)
    return StoreSearchService(repository, StoreProductAccessPolicy(access)), admin


def test_a_phrase_matching_no_single_product_offers_the_closest_matches() -> None:
    projection = AndSemanticsProjection(_catalogue())
    service, admin = _service(projection)

    result = service.search(admin, StoreSearchFilters(query="arctic shipping routes"))

    assert result.relaxed is True
    assert result.total == 2
    assert projection.retrieval_queries == [
        "arctic shipping routes",
        "arctic OR shipping OR routes",
    ]


def test_match_reasons_describe_the_typed_query_not_the_broadened_one() -> None:
    projection = AndSemanticsProjection(_catalogue())
    service, admin = _service(projection)

    result = service.search(admin, StoreSearchFilters(query="arctic shipping routes"))

    reasons = {reason for hit in result.hits for reason in hit.match_reasons}
    assert "full-text:arctic" in reasons
    assert not any(reason.endswith(":or") for reason in reasons)


def test_an_exact_multi_term_match_is_never_reported_as_broadened() -> None:
    projection = AndSemanticsProjection(_catalogue())
    service, admin = _service(projection)

    result = service.search(admin, StoreSearchFilters(query="arctic route"))

    assert result.relaxed is False
    assert result.total == 1
    assert projection.retrieval_queries == ["arctic route"]


def test_a_single_term_with_no_match_stays_an_honest_empty_result() -> None:
    projection = AndSemanticsProjection(_catalogue())
    service, admin = _service(projection)

    result = service.search(admin, StoreSearchFilters(query="submarine"))

    assert result.relaxed is False
    assert result.total == 0
    assert result.hits == ()
    # Broadening a single term would search for exactly the same thing.
    assert projection.retrieval_queries == ["submarine"]


def test_a_multi_term_query_with_no_match_at_all_reports_no_products() -> None:
    projection = AndSemanticsProjection(_catalogue())
    service, admin = _service(projection)

    result = service.search(admin, StoreSearchFilters(query="submarine reactor"))

    assert result.relaxed is False
    assert result.total == 0
    assert projection.retrieval_queries == ["submarine reactor", "submarine OR reactor"]
