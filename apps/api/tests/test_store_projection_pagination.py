from dataclasses import replace
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import Engine

from coeus.core.errors import AppError
from coeus.domain.store import StoreProductSearchPage, StoreSearchFilters
from coeus.persistence.store_projection import PostgresStoreProjection
from coeus.repositories.store import InMemoryStoreRepository
from coeus.services.store import StoreSearchService
from coeus.services.store_product_policy import StoreProductAccessPolicy
from store_projection_helpers import (
    FakeSqlEngine,
    RecordingProjection,
    access_repository,
    empty_visibility_scope,
    seed_product,
    visibility_scope,
)


class SearchRecordingProjection(RecordingProjection):
    def __init__(self) -> None:
        super().__init__()
        self.search_filters: list[StoreSearchFilters] = []

    def search_product_page(
        self, filters: StoreSearchFilters, scope: object
    ) -> StoreProductSearchPage:
        self.search_filters.append(filters)
        return super().search_product_page(filters, scope)


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


def test_store_search_rejects_an_unbounded_result_window_before_projection() -> None:
    access = access_repository()
    admin = access.get_user_by_username("admin@example.test")
    assert admin is not None
    projection = SearchRecordingProjection()
    repository = InMemoryStoreRepository(access, projection=projection)
    service = StoreSearchService(repository, StoreProductAccessPolicy(access))

    with pytest.raises(AppError) as error:
        service.search(
            admin,
            StoreSearchFilters(
                product_type="assessment_report",
                page=101,
                page_size=50,
            ),
        )

    assert error.value.status_code == 422
    assert error.value.code == "store_result_window_exceeded"
    assert projection.search_filters == []


def test_store_search_preserves_the_final_bounded_result_window() -> None:
    access = access_repository()
    admin = access.get_user_by_username("admin@example.test")
    assert admin is not None
    projection = SearchRecordingProjection()
    repository = InMemoryStoreRepository(access, projection=projection)
    service = StoreSearchService(repository, StoreProductAccessPolicy(access))

    result = service.search(
        admin,
        StoreSearchFilters(
            product_type="assessment_report",
            page=100,
            page_size=50,
        ),
    )

    assert result.page == 100
    assert result.page_size == 50
    assert len(projection.search_filters) == 1
    filters = projection.search_filters[0]
    assert (filters.page - 1) * filters.page_size == 4_950


def test_postgres_store_search_sets_a_transaction_local_statement_deadline() -> None:
    product = seed_product()
    engine = FakeSqlEngine((product,))
    projection = PostgresStoreProjection(cast(Engine, engine))

    projection.search_product_page(StoreSearchFilters(), visibility_scope(product))

    deadline_index = next(
        index
        for index, statement in enumerate(engine.statements)
        if "set_config('statement_timeout'" in statement
    )
    summary_index = next(
        index
        for index, statement in enumerate(engine.statements)
        if statement.startswith("WITH filtered_products AS")
    )
    assert deadline_index < summary_index
    assert any(params.get("statement_timeout") == "60000ms" for params in engine.params)


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
