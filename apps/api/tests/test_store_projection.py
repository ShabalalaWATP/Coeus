from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest
from sqlalchemy.engine import Engine

from coeus.core.errors import AppError
from coeus.persistence.state_store import MemoryStateStore
from coeus.persistence.store_projection import PostgresStoreProjection
from coeus.repositories.store import InMemoryStoreRepository
from coeus.services.asset_tokens import AssetTokenService
from coeus.services.audit import AuditLog
from coeus.services.store import StoreProductAccessPolicy, StoreSearchService
from coeus.services.store_access import StoreAssetService, StoreDetailService
from store_projection_helpers import (
    FakeSqlEngine,
    RecordingProjection,
    access_repository,
    empty_visibility_scope,
    filters,
    seed_product,
    visibility_scope,
)


def test_store_repository_mirrors_seed_products_to_projection() -> None:
    projection = RecordingProjection()

    repository = InMemoryStoreRepository(access_repository(), projection=projection)

    assert len(repository.list_products()) == 3
    assert len(projection.saved_batches) == 1
    assert len(projection.saved_batches[0]) == 3


def test_store_repository_restores_projection_before_json_state() -> None:
    source = InMemoryStoreRepository(access_repository())
    projected_product = replace(source.list_products()[0], reference="PROD-1100")
    projection = RecordingProjection((projected_product,))
    state_store = MemoryStateStore()
    state_store.save("store", {"reference_counter": 1003, "products": []})

    repository = InMemoryStoreRepository(access_repository(), state_store, projection)

    assert repository.list_products() == (projected_product,)
    assert repository.next_reference() == "PROD-1101"
    payload = state_store.load("store")
    assert payload is not None
    assert len(payload["products"]) == 1
    assert projection.saved_batches == [(projected_product,)]


def test_store_repository_persists_saved_products_to_projection() -> None:
    projection = RecordingProjection()
    repository = InMemoryStoreRepository(access_repository(), projection=projection)
    product = repository.list_products()[0]
    updated = replace(product, metadata=replace(product.metadata, title="Updated title"))

    repository.save_product(updated)

    saved_titles = {product.metadata.title for product in projection.saved_batches[-1]}
    assert "Updated title" in saved_titles


def test_store_repository_reads_latest_projection_products() -> None:
    projection = RecordingProjection()
    repository = InMemoryStoreRepository(access_repository(), projection=projection)
    external = replace(repository.list_products()[0], reference="PROD-1200")

    projection.products = (external,)

    assert repository.list_products() == (external,)
    assert repository.get_product(external.product_id) == external
    assert repository.next_reference() == "PROD-1201"


def test_store_repository_uses_projection_search_with_visibility_scope() -> None:
    source = InMemoryStoreRepository(access_repository())
    product = source.list_products()[0]
    projection = RecordingProjection((product,))
    repository = InMemoryStoreRepository(access_repository(), projection=projection)
    scope = visibility_scope(product)

    assert repository.search_products(filters(), scope) == (product,)


def test_store_repository_uses_projection_visible_product_with_visibility_scope() -> None:
    source = InMemoryStoreRepository(access_repository())
    product = source.list_products()[0]
    repository = InMemoryStoreRepository(
        access_repository(), projection=RecordingProjection((product,))
    )

    assert repository.get_visible_product(product.product_id, visibility_scope(product)) == product


def test_postgres_store_projection_searches_with_access_predicates() -> None:
    product = seed_product()
    engine = FakeSqlEngine((product,))
    projection = PostgresStoreProjection(cast(Engine, engine))

    results = projection.search_products(filters(query="assessment"), visibility_scope(product))
    blocked = projection.search_products(filters(query="assessment"), empty_visibility_scope())

    assert results == (product,)
    assert blocked == ()
    sql = "\n".join(engine.statements)
    assert "p.classification_level <= :clearance_level" in sql
    assert "product_acg.acg_id = ANY(CAST(:acg_ids AS uuid[]))" in sql
    assert "websearch_to_tsquery" in sql


def test_postgres_store_projection_hybrid_candidates_keep_access_predicates() -> None:
    product = seed_product()
    engine = FakeSqlEngine((product,))
    projection = PostgresStoreProjection(cast(Engine, engine))

    results = projection.hybrid_candidates(
        filters(),
        visibility_scope(product),
        "boat traffic",
        (0.01,) * 384,
    )
    blocked = projection.hybrid_candidates(filters(), empty_visibility_scope(), "boat", None)

    assert len(results) == 1
    assert blocked == ()
    sql = "\n".join(engine.statements)
    assert "WITH scoped AS" in sql
    assert "p.classification_level <= :clearance_level" in sql
    assert "product_acg.acg_id = ANY(CAST(:acg_ids AS uuid[]))" in sql
    assert "websearch_to_tsquery" in sql
    assert "embedding <=> CAST(:query_embedding AS vector)" in sql


def test_postgres_store_projection_gets_visible_product_with_access_predicates() -> None:
    product = seed_product()
    engine = FakeSqlEngine((product,))
    projection = PostgresStoreProjection(cast(Engine, engine))

    visible = projection.get_visible_product(product.product_id, visibility_scope(product))
    blocked = projection.get_visible_product(product.product_id, empty_visibility_scope())

    assert visible == product
    assert blocked is None
    sql = "\n".join(engine.statements)
    assert "p.product_id = CAST(:product_id AS uuid)" in sql
    assert "product_acg.acg_id = ANY(CAST(:acg_ids AS uuid[]))" in sql


def test_store_search_rechecks_policy_after_projection_candidates() -> None:
    access_repo = access_repository()
    user = access_repo.get_user_by_username("user@example.test")
    assert user is not None
    source = InMemoryStoreRepository(access_repo)
    restricted = next(
        product
        for product in source.list_products()
        if product.metadata.title == "Collection Sensor Summary"
    )
    repository = InMemoryStoreRepository(access_repo, projection=RecordingProjection((restricted,)))
    service = StoreSearchService(repository, StoreProductAccessPolicy(access_repo))

    result = service.search(user, filters())

    assert result.total == 0
    assert result.facets.product_types == ()


def test_store_detail_and_download_recheck_policy_after_projection_candidate() -> None:
    access_repo = access_repository()
    user = access_repo.get_user_by_username("user@example.test")
    assert user is not None
    source = InMemoryStoreRepository(access_repo)
    restricted = next(
        product
        for product in source.list_products()
        if product.metadata.title == "Collection Sensor Summary"
    )
    repository = InMemoryStoreRepository(access_repo, projection=RecordingProjection((restricted,)))
    details = StoreDetailService(
        repository,
        StoreProductAccessPolicy(access_repo),
        AuditLog(),
    )
    assets = StoreAssetService(details, AssetTokenService("test-token-secret"), AuditLog())

    with pytest.raises(AppError) as detail_error:
        details.get_visible_product(user, restricted.product_id)
    with pytest.raises(AppError) as asset_error:
        assets.grant_access(user, restricted.product_id, restricted.assets[0].asset_id)

    assert detail_error.value.code == "product_not_found"
    assert asset_error.value.code == "product_not_found"


def test_postgres_store_projection_decodes_products_from_relational_rows() -> None:
    product = seed_product()
    engine = FakeSqlEngine((product,))
    projection = PostgresStoreProjection(cast(Engine, engine))

    loaded = projection.list_products()

    assert loaded == (product,)
    assert any("FROM intelligence_store_products" in statement for statement in engine.statements)


def test_postgres_store_projection_upserts_product_and_children() -> None:
    product = seed_product()
    old_product = replace(product, metadata=replace(product.metadata, semantic_labels=frozenset()))
    engine = FakeSqlEngine()
    projection = PostgresStoreProjection(cast(Engine, engine))

    projection.save_product(old_product)
    projection.save_products((product,))
    projection.save_products(())

    sql = "\n".join(engine.statements)
    assert "ON CONFLICT (product_id)" in sql
    assert "DELETE FROM intelligence_store_products" in sql
    assert "intelligence_store_assets" in sql
    assert "intelligence_store_product_acgs" in sql
    assert "intelligence_store_semantic_labels" in sql
    assert "embedding = EXCLUDED.embedding" in sql
    assert any(params.get("reference") == product.reference for params in engine.params)
    assert any("embedding" in params for params in engine.params)
    assert any(params.get("label") == "assessment" for params in engine.params)
