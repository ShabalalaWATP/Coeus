from dataclasses import replace
from typing import cast
from uuid import uuid4

from sqlalchemy.engine import Engine

from coeus.persistence.store_projection import PostgresStoreProjection
from store_projection_helpers import FakeSqlEngine, seed_product, visibility_scope


def test_postgres_batch_visibility_uses_constant_query_count() -> None:
    first = seed_product()
    second = replace(
        first,
        product_id=uuid4(),
        reference="PROD-BATCH-2",
        metadata=replace(first.metadata, title="Second batch product"),
    )
    engine = FakeSqlEngine((first, second))
    projection = PostgresStoreProjection(cast(Engine, engine))

    products = projection.get_visible_products(
        frozenset({first.product_id, second.product_id}), visibility_scope(first)
    )

    assert products == (first, second)
    store_selects = [
        statement
        for statement in engine.statements
        if statement.startswith("SELECT")
        and (
            "intelligence_store_products" in statement
            or "intelligence_store_assets" in statement
            or "intelligence_store_product_acgs" in statement
            or "intelligence_store_semantic_labels" in statement
        )
    ]
    assert len(store_selects) == 4
    assert "p.product_id = ANY(CAST(:product_ids AS uuid[]))" in store_selects[0]
    product_id_batches = [
        params["product_ids"] for params in engine.params if "product_ids" in params
    ]
    assert len(product_id_batches) == 4
    assert all(
        set(batch) == {str(first.product_id), str(second.product_id)}
        for batch in product_id_batches
    )
