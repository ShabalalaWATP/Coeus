"""The chunk index must pre-filter both legs by ACG and clearance in SQL."""

from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from coeus.domain.access import ProductStatus
from coeus.domain.search_index import SearchChunk, SearchChunkEmbedding, SearchIndexProfile
from coeus.domain.store import StoreProduct, StoreVisibilityScope
from coeus.persistence.search_index_postgres import PostgresSearchIndexRepository
from coeus.persistence.search_index_validation import embedding_source_hash
from coeus.persistence.store_projection import PostgresStoreProjection
from coeus.services.search_configuration import SEARCH_EMBEDDING_DIMENSIONS
from store_projection_helpers import seed_product

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


def test_chunk_search_excludes_unauthorised_acg_and_clearance_in_both_legs(
    postgres_database_url: str,
) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", postgres_database_url)
    command.upgrade(config, "head")
    engine = create_engine(postgres_database_url)
    authorised_acg = uuid4()
    other_acg = uuid4()
    base = seed_product()
    visible = _variant(base, acg_ids=frozenset({authorised_acg}), classification=2)
    wrong_acg = _variant(base, acg_ids=frozenset({other_acg}), classification=2)
    above_clearance = _variant(base, acg_ids=frozenset({authorised_acg}), classification=5)
    products = (visible, wrong_acg, above_clearance)
    repository = PostgresSearchIndexRepository(engine)
    try:
        PostgresStoreProjection(engine).save_products(products)
        chunks = tuple(_chunk(product.product_id) for product in products)
        profile = _profile()
        repository.begin(profile)
        repository.activate(
            replace(profile, status="ready", is_active=True, completed_at=datetime.now(UTC)),
            chunks,
            tuple(
                SearchChunkEmbedding(
                    chunk.chunk_id,
                    embedding_source_hash(profile.space_id, chunk.content_hash),
                    _unit_vector(),
                )
                for chunk in chunks
            ),
        )

        hits = repository.search(
            StoreVisibilityScope(
                acg_ids=frozenset({authorised_acg}),
                clearance_level=2,
                include_drafts=False,
            ),
            "synthetic armour",
            _unit_vector(),
        )

        # All three chunks share identical text and vectors: without the SQL
        # pre-filter every leg would return all of them.
        assert [hit.product_id for hit in hits] == [visible.product_id]
        assert hits[0].lexical_rank == 1
        assert hits[0].vector_rank == 1
    finally:
        engine.dispose()


def _variant(base: StoreProduct, *, acg_ids: frozenset[UUID], classification: int) -> StoreProduct:
    return replace(
        base,
        product_id=uuid4(),
        reference=f"PROD-{uuid4().hex[:8].upper()}",
        assets=(),
        metadata=replace(
            base.metadata,
            acg_ids=acg_ids,
            classification_level=classification,
            status=ProductStatus.PUBLISHED,
        ),
    )


def _chunk(product_id: UUID) -> SearchChunk:
    content = "MOCK DATA ONLY synthetic armour movement summary."
    return SearchChunk(
        chunk_id=uuid4(),
        product_id=product_id,
        asset_id=None,
        asset_name="inline",
        asset_sha256=None,
        page_number=1,
        chunk_index=0,
        content=content,
        content_hash=sha256(content.encode()).hexdigest(),
        extractor_version="extractor-test-v1",
        chunker_version="chunker-test-v1",
    )


def _profile() -> SearchIndexProfile:
    return SearchIndexProfile(
        profile_id=uuid4(),
        provider="mock",
        model="token-hash-v2",
        dimensions=SEARCH_EMBEDDING_DIMENSIONS,
        generation=1,
        space_id=f"mock:token-hash-v2:1536:{uuid4()}",
        status="indexing",
        is_active=False,
        corpus_version="postgres-chunk-access-test",
        product_count=3,
        chunk_count=3,
        indexed_count=3,
        failed_count=0,
        created_by_user_id=uuid4(),
        created_at=datetime.now(UTC),
    )


def _unit_vector() -> tuple[float, ...]:
    return (1.0, *((0.0,) * (SEARCH_EMBEDDING_DIMENSIONS - 1)))
