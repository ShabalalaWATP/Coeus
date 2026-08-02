"""Sorting, facet counting and broadened-query behaviour for Store search."""

from dataclasses import replace
from uuid import uuid4

from coeus.domain.store import (
    StoreFacetValue,
    StoreProduct,
    StoreSearchFilters,
    StoreSearchHit,
    StoreSortOrder,
)
from coeus.services.store_search_results import (
    facets_for,
    paged_result,
    relaxed_query,
    sort_hits,
)
from store_projection_helpers import seed_product


def _product(
    title: str,
    *,
    coverage_start: str | None = None,
    product_type: str = "assessment_report",
    region: str = "Baltic ports",
    tags: tuple[str, ...] = ("ports",),
) -> StoreProduct:
    base = seed_product()
    return replace(
        base,
        product_id=uuid4(),
        metadata=replace(
            base.metadata,
            title=title,
            product_type=product_type,
            area_or_region=region,
            tags=frozenset(tags),
            time_period_start=coverage_start,
        ),
    )


def _hit(product: StoreProduct, score: float) -> StoreSearchHit:
    return StoreSearchHit(product=product, match_score=score, match_reasons=("visible",))


def test_title_sort_is_case_insensitive_and_ignores_relevance() -> None:
    hits = (
        _hit(_product("zulu report"), 0.9),
        _hit(_product("Alpha report"), 0.1),
        _hit(_product("mike report"), 0.5),
    )

    ordered = sort_hits(hits, StoreSortOrder.TITLE)

    assert [hit.product.metadata.title for hit in ordered] == [
        "Alpha report",
        "mike report",
        "zulu report",
    ]


def test_coverage_sort_is_newest_first_and_undated_products_sort_last() -> None:
    hits = (
        _hit(_product("Older", coverage_start="2025-01-01"), 0.9),
        _hit(_product("Undated", coverage_start=None), 0.9),
        _hit(_product("Newest", coverage_start="2026-07-01"), 0.1),
    )

    ordered = sort_hits(hits, StoreSortOrder.COVERAGE)

    assert [hit.product.metadata.title for hit in ordered] == ["Newest", "Older", "Undated"]


def test_coverage_sort_breaks_ties_on_title() -> None:
    hits = (
        _hit(_product("Zulu", coverage_start="2026-01-01"), 0.9),
        _hit(_product("Alpha", coverage_start="2026-01-01"), 0.1),
        _hit(_product("Mike", coverage_start="2026-01-01"), 0.5),
    )

    ordered = sort_hits(hits, StoreSortOrder.COVERAGE)

    assert [hit.product.metadata.title for hit in ordered] == ["Alpha", "Mike", "Zulu"]


def test_coverage_sort_keeps_undated_products_in_title_order() -> None:
    hits = (
        _hit(_product("Zulu", coverage_start=None), 0.9),
        _hit(_product("Alpha", coverage_start=None), 0.1),
    )

    ordered = sort_hits(hits, StoreSortOrder.COVERAGE)

    assert [hit.product.metadata.title for hit in ordered] == ["Alpha", "Zulu"]


def test_relevance_sort_keeps_score_order() -> None:
    hits = (_hit(_product("Alpha"), 0.2), _hit(_product("Zulu"), 0.8))

    ordered = sort_hits(hits, StoreSortOrder.RELEVANCE)

    assert [hit.product.metadata.title for hit in ordered] == ["Zulu", "Alpha"]


def test_sort_applies_across_pages_not_just_the_current_page() -> None:
    hits = tuple(
        _hit(_product(f"Product {index}", coverage_start=f"202{index}-01-01"), 0.5)
        for index in range(5)
    )
    filters = StoreSearchFilters(page=2, page_size=2, sort=StoreSortOrder.COVERAGE)

    result = paged_result(hits, filters, facets_for(()))

    # Newest first across the whole result set: page 2 holds the third and
    # fourth newest, which a page-local sort could never produce.
    assert [hit.product.metadata.title for hit in result.hits] == ["Product 2", "Product 1"]
    assert result.total == 5
    assert result.total_pages == 3


def test_facets_count_every_visible_product() -> None:
    products = (
        _product("One", product_type="assessment_report", region="Baltic ports", tags=("ports",)),
        _product("Two", product_type="assessment_report", region="Arctic Circle", tags=("ports",)),
        _product("Three", product_type="sigint_mock", region="Arctic Circle", tags=("signals",)),
    )

    facets = facets_for(products)

    assert facets.product_types == (
        StoreFacetValue("assessment_report", 2),
        StoreFacetValue("sigint_mock", 1),
    )
    assert facets.regions == (
        StoreFacetValue("Arctic Circle", 2),
        StoreFacetValue("Baltic ports", 1),
    )
    assert facets.tags == (StoreFacetValue("ports", 2), StoreFacetValue("signals", 1))


def test_facets_of_no_products_are_empty() -> None:
    facets = facets_for(())

    assert facets.product_types == ()
    assert facets.regions == ()
    assert facets.tags == ()


def test_relaxed_query_joins_multiple_terms_with_or() -> None:
    assert relaxed_query("arctic shipping routes") == "arctic OR shipping OR routes"


def test_relaxed_query_is_none_when_broadening_would_change_nothing() -> None:
    assert relaxed_query("arctic") is None
    assert relaxed_query("  ") is None
    # Stop words are not terms, so this stays a single-term query.
    assert relaxed_query("the arctic") is None


def test_relaxed_query_does_not_repeat_duplicate_terms() -> None:
    assert relaxed_query("arctic arctic shipping") == "arctic OR shipping"


def test_paged_result_reports_a_broadened_search() -> None:
    hits = (_hit(_product("Arctic Route Bundle"), 0.4),)

    exact = paged_result(hits, StoreSearchFilters(), facets_for(()))
    broadened = paged_result(hits, StoreSearchFilters(), facets_for(()), relaxed=True)

    assert exact.relaxed is False
    assert broadened.relaxed is True
