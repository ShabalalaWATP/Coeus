"""Execute the browse ORDER BY variants and facet-count aggregation for real.

The default test suite runs the memory persistence provider, so the Python
ranking path answers every browse query and these SQL statements are never
executed. A syntax slip, a `NULLS LAST` mistake or a `jsonb_agg` shape change
would therefore reach a PostgreSQL deployment unnoticed.
"""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from coeus.domain.access import ProductStatus
from coeus.domain.store import (
    StoreFacetValue,
    StoreProduct,
    StoreProductMetadata,
    StoreSearchFilters,
    StoreSortOrder,
    StoreVisibilityScope,
)
from coeus.persistence.relational_schema import ensure_relational_schema
from coeus.persistence.store_projection_search import search_product_page
from coeus.persistence.store_projection_write import save_product

API_ROOT = Path(__file__).resolve().parents[2]
ACG_ID = uuid4()
REGION = "Baltic approaches"


def _product(reference: str, title: str, coverage_start: str | None, tag: str) -> StoreProduct:
    now = datetime.now(UTC)
    return StoreProduct(
        product_id=uuid4(),
        reference=reference,
        metadata=StoreProductMetadata(
            title=title,
            summary="MOCK DATA ONLY synthetic sort fixture.",
            description="MOCK DATA ONLY synthetic sort fixture.",
            product_type="assessment_report",
            source_type="finished_assessment",
            owner_team="RFA",
            area_or_region=REGION,
            classification_level=1,
            releasability=frozenset({"MOCK"}),
            handling_caveats=frozenset({"MOCK DATA ONLY"}),
            tags=frozenset({tag}),
            acg_ids=frozenset({ACG_ID}),
            status=ProductStatus.PUBLISHED,
            time_period_start=coverage_start,
            time_period_end=coverage_start,
            geojson_ref=None,
            bounding_box=None,
            semantic_labels=frozenset(),
        ),
        assets=(),
        created_by_user_id=uuid4(),
        created_at=now,
        updated_at=now,
    )


CATALOGUE = (
    _product("PROD-SQL-1", "Zulu oldest", "2025-01-01", "alpha-tag"),
    _product("PROD-SQL-2", "Alpha newest", "2026-07-01", "alpha-tag"),
    _product("PROD-SQL-3", "Mike undated", None, "beta-tag"),
)


def _engine(database_url: str):
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        ensure_relational_schema(connection)
        for product in CATALOGUE:
            save_product(connection, product, None, {})
    return engine


def _scope() -> StoreVisibilityScope:
    return StoreVisibilityScope(
        acg_ids=frozenset({ACG_ID}),
        clearance_level=5,
        include_drafts=False,
    )


@pytest.mark.postgres
def test_sql_coverage_sort_is_newest_first_with_undated_products_last(
    postgres_database_url: str,
) -> None:
    engine = _engine(postgres_database_url)
    try:
        with engine.begin() as connection:
            page = search_product_page(
                connection,
                StoreSearchFilters(sort=StoreSortOrder.COVERAGE, page_size=10),
                _scope(),
            )
    finally:
        engine.dispose()

    assert [product.metadata.title for product in page.products] == [
        "Alpha newest",
        "Zulu oldest",
        "Mike undated",
    ]


@pytest.mark.postgres
def test_sql_title_and_relevance_sorts_both_order_by_title(
    postgres_database_url: str,
) -> None:
    engine = _engine(postgres_database_url)
    expected = ["Alpha newest", "Mike undated", "Zulu oldest"]
    try:
        with engine.begin() as connection:
            titled = search_product_page(
                connection,
                StoreSearchFilters(sort=StoreSortOrder.TITLE, page_size=10),
                _scope(),
            )
            # Catalogue browse has no relevance signal, so it falls back to
            # the same deterministic title order.
            relevance = search_product_page(
                connection,
                StoreSearchFilters(sort=StoreSortOrder.RELEVANCE, page_size=10),
                _scope(),
            )
    finally:
        engine.dispose()

    assert [product.metadata.title for product in titled.products] == expected
    assert [product.metadata.title for product in relevance.products] == expected


@pytest.mark.postgres
def test_every_sort_order_has_an_executable_statement(postgres_database_url: str) -> None:
    engine = _engine(postgres_database_url)
    try:
        with engine.begin() as connection:
            totals = {
                sort: search_product_page(
                    connection, StoreSearchFilters(sort=sort, page_size=10), _scope()
                ).total
                for sort in StoreSortOrder
            }
    finally:
        engine.dispose()

    assert totals == {sort: len(CATALOGUE) for sort in StoreSortOrder}


@pytest.mark.postgres
def test_sql_facet_counts_cover_the_whole_filtered_set(postgres_database_url: str) -> None:
    engine = _engine(postgres_database_url)
    try:
        with engine.begin() as connection:
            # One product per page, so counts cannot be coming from the page.
            page = search_product_page(connection, StoreSearchFilters(page_size=1), _scope())
    finally:
        engine.dispose()

    assert len(page.products) == 1
    assert page.total == len(CATALOGUE)
    assert page.facets.product_types == (StoreFacetValue("assessment_report", 3),)
    assert page.facets.regions == (StoreFacetValue(REGION, 3),)
    assert page.facets.tags == (StoreFacetValue("alpha-tag", 2), StoreFacetValue("beta-tag", 1))
