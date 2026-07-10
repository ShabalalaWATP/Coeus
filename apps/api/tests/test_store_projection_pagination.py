from dataclasses import replace
from typing import cast
from uuid import uuid4

from sqlalchemy.engine import Engine

from coeus.domain.store import StoreSearchFilters
from coeus.persistence.store_projection import PostgresStoreProjection
from coeus.repositories.store import InMemoryStoreRepository
from store_projection_helpers import (
    FakeSqlEngine,
    RecordingProjection,
    access_repository,
    empty_visibility_scope,
    seed_product,
    visibility_scope,
)


def test_store_repository_uses_projection_page_with_visibility_scope() -> None:
    source = InMemoryStoreRepository(access_repository())
    product = source.list_products()[0]
    projection = RecordingProjection((product,))
    repository = InMemoryStoreRepository(access_repository(), projection=projection)

    page = repository.search_product_page(StoreSearchFilters(), visibility_scope(product))

    assert page is not None
    assert page.products == (product,)
    assert page.total == 1


def test_postgres_store_projection_pages_before_child_hydration() -> None:
    first = seed_product()
    products = tuple(
        replace(
            first,
            product_id=uuid4(),
            reference=f"PROD-PAGE-{index}",
            metadata=replace(first.metadata, title=f"Page product {index}"),
        )
        for index in range(3)
    )
    engine = FakeSqlEngine(products)
    projection = PostgresStoreProjection(cast(Engine, engine))

    page = projection.search_product_page(
        StoreSearchFilters(page=2, page_size=1), visibility_scope(first)
    )

    assert page.products == (products[1],)
    assert page.total == 3
    assert page.facets.product_types == (first.metadata.product_type,)
    sql = "\n".join(engine.statements)
    assert "p.classification_level <= :clearance_level" in sql
    assert "product_acg.acg_id = ANY(CAST(:acg_ids AS uuid[]))" in sql
    assert "LIMIT :page_size" in sql
    assert "OFFSET :offset" in sql
    child_batches = [params["product_ids"] for params in engine.params if "product_ids" in params]
    assert child_batches == [[str(products[1].product_id)]] * 3


def test_postgres_store_projection_returns_empty_page_without_visibility() -> None:
    product = seed_product()
    projection = PostgresStoreProjection(cast(Engine, FakeSqlEngine((product,))))

    page = projection.search_product_page(StoreSearchFilters(), empty_visibility_scope())

    assert page.products == ()
    assert page.total == 0


def test_postgres_store_projection_handles_empty_authorised_queries() -> None:
    product = seed_product()
    projection = PostgresStoreProjection(cast(Engine, FakeSqlEngine()))
    scope = visibility_scope(product)

    assert projection.get_visible_product(uuid4(), scope) is None
    assert projection.search_product_page(StoreSearchFilters(), scope).products == ()
    assert projection.hybrid_candidates(StoreSearchFilters(), scope, "query", None) == ()
