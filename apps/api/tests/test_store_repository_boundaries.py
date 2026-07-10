from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import Engine

from coeus.persistence.store_projection import PostgresStoreProjection
from coeus.persistence.store_projection_write import _encode_bounding_box
from coeus.repositories.store import InMemoryStoreRepository
from store_projection_helpers import (
    FakeSqlEngine,
    RecordingProjection,
    access_repository,
    seed_product,
    visibility_scope,
)


def test_store_repository_handles_missing_products_and_embedding_delegation() -> None:
    product = seed_product()
    projection = RecordingProjection((product,))
    repository = InMemoryStoreRepository(access_repository(), projection=projection)

    assert repository.get_visible_product(uuid4(), visibility_scope(product)) is None
    repository.delete_product(uuid4())
    assert repository.embedded_product_count() == 1
    assert repository.backfill_missing_embeddings(batch_size=1) == 1

    without_projection = InMemoryStoreRepository(access_repository())
    assert without_projection.embedded_product_count() == 0
    assert without_projection.backfill_missing_embeddings() == 0


def test_store_repository_initialisation_guard_skips_persistence() -> None:
    projection = RecordingProjection()
    repository = InMemoryStoreRepository(access_repository(), projection=projection)
    saved_before = len(projection.saved_batches)

    repository._initialising = True
    repository._persist()

    assert len(projection.saved_batches) == saved_before


def test_projection_backfill_handles_missing_products_and_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = FakeSqlEngine()
    projection = PostgresStoreProjection(cast(Engine, engine))
    missing_id = uuid4()
    monkeypatch.setattr(projection, "_missing_embedding_ids", lambda _batch: (missing_id,))

    assert projection.backfill_missing_embeddings() == 0
    with (
        engine.begin() as connection,
        pytest.raises(RuntimeError, match="embedding provider is required"),
    ):
        projection._backfill_product(connection, seed_product())
    assert _encode_bounding_box(None) is None
