from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from typing import cast

import pytest
from sqlalchemy.engine import Engine

from coeus.core.errors import AppError
from coeus.domain.store import StoreProduct
from coeus.persistence.state_store import MemoryStateStore
from coeus.persistence.store_projection import PostgresStoreProjection
from coeus.repositories.store import InMemoryStoreRepository
from coeus.services.asset_tokens import AssetTokenService
from coeus.services.audit import AuditLog
from coeus.services.embeddings import EmbeddingService
from coeus.services.store import StoreSearchService
from coeus.services.store_access import StoreAssetService, StoreDetailService
from coeus.services.store_product_policy import StoreProductAccessPolicy
from coeus.services.store_semantics import product_semantic_text
from store_projection_helpers import (
    FakeEmbeddingService,
    FakeSqlEngine,
    RecordingProjection,
    access_repository,
    empty_visibility_scope,
    filters,
    seed_product,
    visibility_scope,
)


def _semantic_hash(product: StoreProduct) -> str:
    return sha256(product_semantic_text(product).encode("utf-8")).hexdigest()


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


def test_store_repository_uses_projection_visible_product_with_visibility_scope() -> None:
    source = InMemoryStoreRepository(access_repository())
    product = source.list_products()[0]
    repository = InMemoryStoreRepository(
        access_repository(), projection=RecordingProjection((product,))
    )

    assert repository.get_visible_product(product.product_id, visibility_scope(product)) == product


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
    assert "embedding IS NOT NULL" in sql
    assert ">= :vector_similarity_floor" in sql
    assert "SELECT product_id FROM lexical" in sql
    assert "UNION" in sql
    assert "SELECT product_id FROM semantic" in sql
    assert "JOIN selected ON selected.product_id = scoped.product_id" in sql
    assert any(params.get("leg_limit") == 50 for params in engine.params)
    assert any("vector_similarity_floor" in params for params in engine.params)


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
    assert (
        "embedding = COALESCE(CAST(:embedding AS vector), intelligence_store_products.embedding)"
        in sql
    )
    assert "embedding = EXCLUDED.embedding" not in sql
    assert any(params.get("reference") == product.reference for params in engine.params)
    assert any("embedding" in params for params in engine.params)
    assert any(params.get("label") == "assessment" for params in engine.params)


def _projection_with_embeddings(
    engine: FakeSqlEngine, embeddings: FakeEmbeddingService
) -> PostgresStoreProjection:
    return PostgresStoreProjection(cast(Engine, engine), cast(EmbeddingService, embeddings))


def _last_upsert_params(engine: FakeSqlEngine) -> dict[str, object]:
    return [params for params in engine.params if "embedding_source_hash" in params][-1]


def test_unchanged_product_skips_re_embedding() -> None:
    product = seed_product()
    engine = FakeSqlEngine((product,), embedded={str(product.product_id): _semantic_hash(product)})
    embeddings = FakeEmbeddingService()
    projection = _projection_with_embeddings(engine, embeddings)

    projection.save_product(product)

    assert embeddings.calls == []
    params = _last_upsert_params(engine)
    assert params["embedding"] is None
    assert params["embedding_source_hash"] is None


def test_changed_product_is_re_embedded_and_stores_new_hash() -> None:
    product = seed_product()
    engine = FakeSqlEngine((product,), embedded={str(product.product_id): "stale-hash"})
    embeddings = FakeEmbeddingService()
    projection = _projection_with_embeddings(engine, embeddings)

    projection.save_product(product)

    assert len(embeddings.calls) == 1
    params = _last_upsert_params(engine)
    assert params["embedding"] is not None
    assert params["embedding_source_hash"] == _semantic_hash(product)


def test_failed_embedding_does_not_overwrite_stored_vector() -> None:
    product = seed_product()
    engine = FakeSqlEngine((product,), embedded={str(product.product_id): "stale-hash"})
    embeddings = FakeEmbeddingService(vector=None)
    projection = _projection_with_embeddings(engine, embeddings)

    projection.save_product(product)

    # The provider was consulted (text changed) but returned nothing, so the
    # upsert passes a NULL embedding and relies on COALESCE to keep the vector.
    assert embeddings.calls
    params = _last_upsert_params(engine)
    assert params["embedding"] is None
    assert params["embedding_source_hash"] is None
    assert str(product.product_id) in engine.embedding_hashes


def test_embedded_product_count_reflects_embedded_rows() -> None:
    product = seed_product()
    engine = FakeSqlEngine((product,), embedded={str(product.product_id): "hash"})
    projection = PostgresStoreProjection(cast(Engine, engine))

    assert projection.embedded_product_count() == 1


def test_backfill_embeds_all_missing_products_across_batches() -> None:
    products = InMemoryStoreRepository(access_repository()).list_products()
    engine = FakeSqlEngine(products)
    embeddings = FakeEmbeddingService()
    projection = _projection_with_embeddings(engine, embeddings)

    updated = projection.backfill_missing_embeddings(batch_size=1)

    assert updated == len(products)
    assert set(engine.embedding_hashes) == {str(product.product_id) for product in products}
    embeddings.calls.clear()
    assert projection.backfill_missing_embeddings(batch_size=1) == 0
    assert embeddings.calls == []


def test_backfill_stops_when_provider_unavailable() -> None:
    products = InMemoryStoreRepository(access_repository()).list_products()
    engine = FakeSqlEngine(products)
    embeddings = FakeEmbeddingService(vector=None)
    projection = _projection_with_embeddings(engine, embeddings)

    assert projection.backfill_missing_embeddings() == 0
    assert engine.embedding_hashes == {}


def test_backfill_without_embeddings_is_noop() -> None:
    engine = FakeSqlEngine((seed_product(),))
    projection = PostgresStoreProjection(cast(Engine, engine))

    assert projection.backfill_missing_embeddings() == 0
