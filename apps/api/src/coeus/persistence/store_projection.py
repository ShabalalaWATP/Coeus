from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, Result

from coeus.domain.store import (
    StoreHybridCandidate,
    StoreProduct,
    StoreSearchFilters,
    StoreVisibilityScope,
)
from coeus.persistence.relational_schema import ensure_relational_schema
from coeus.persistence.store_projection_decode import decode_product
from coeus.persistence.store_projection_sql import (
    SELECT_ACGS_SQL,
    SELECT_ASSETS_SQL,
    SELECT_LABELS_SQL,
    SELECT_MISSING_EMBEDDING_IDS_SQL,
    SELECT_PRODUCTS_SQL,
    UPDATE_PRODUCT_EMBEDDING_SQL,
)
from coeus.persistence.store_projection_write import (
    delete_stale_products,
    existing_embedding_hashes,
    save_product,
    semantic_hash,
)
from coeus.services.embeddings import EmbeddingService, vector_to_pg
from coeus.services.store_semantics import product_semantic_text


class PostgresStoreProjection:
    def __init__(self, engine: Engine, embeddings: EmbeddingService | None = None) -> None:
        self._engine = engine
        self._embeddings = embeddings

    def list_products(self) -> tuple[StoreProduct, ...]:
        with self._engine.begin() as connection:
            ensure_relational_schema(connection)
            product_rows = _mapping_rows(connection.execute(text(SELECT_PRODUCTS_SQL)))
            asset_rows = _mapping_rows(connection.execute(text(SELECT_ASSETS_SQL)))
            acg_rows = _mapping_rows(connection.execute(text(SELECT_ACGS_SQL)))
            label_rows = _mapping_rows(connection.execute(text(SELECT_LABELS_SQL)))
        return tuple(decode_product(row, asset_rows, acg_rows, label_rows) for row in product_rows)

    def search_products(
        self, filters: StoreSearchFilters, scope: StoreVisibilityScope
    ) -> tuple[StoreProduct, ...]:
        from coeus.persistence.store_projection_search import search_products

        with self._engine.begin() as connection:
            ensure_relational_schema(connection)
            return search_products(connection, filters, scope)

    def hybrid_candidates(
        self,
        filters: StoreSearchFilters,
        scope: StoreVisibilityScope,
        query: str,
        query_embedding: tuple[float, ...] | None,
        leg_limit: int = 50,
    ) -> tuple[StoreHybridCandidate, ...]:
        from coeus.persistence.store_projection_search import hybrid_candidates

        with self._engine.begin() as connection:
            ensure_relational_schema(connection)
            return hybrid_candidates(
                connection,
                filters,
                scope,
                query,
                vector_to_pg(query_embedding),
                leg_limit,
            )

    def get_visible_product(
        self, product_id: UUID, scope: StoreVisibilityScope
    ) -> StoreProduct | None:
        from coeus.persistence.store_projection_search import get_visible_product

        with self._engine.begin() as connection:
            ensure_relational_schema(connection)
            return get_visible_product(connection, product_id, scope)

    def save_product(self, product: StoreProduct) -> None:
        with self._engine.begin() as connection:
            ensure_relational_schema(connection)
            existing = existing_embedding_hashes(connection, (product.product_id,))
            save_product(connection, product, self._embeddings, existing)

    def save_products(self, products: tuple[StoreProduct, ...]) -> None:
        with self._engine.begin() as connection:
            ensure_relational_schema(connection)
            delete_stale_products(connection, products)
            existing = existing_embedding_hashes(
                connection, tuple(product.product_id for product in products)
            )
            for product in products:
                save_product(connection, product, self._embeddings, existing)

    def embedded_product_count(self) -> int:
        with self._engine.begin() as connection:
            ensure_relational_schema(connection)
            row = connection.execute(
                text(
                    """
                    SELECT count(*) AS count
                    FROM intelligence_store_products
                    WHERE embedding IS NOT NULL
                    """
                )
            ).first()
        return int(row[0]) if row is not None else 0

    def backfill_missing_embeddings(self, batch_size: int = 500) -> int:
        if self._embeddings is None:
            return 0
        products = {product.product_id: product for product in self.list_products()}
        updated = 0
        while True:
            missing = self._missing_embedding_ids(batch_size)
            if not missing:
                break
            embedded_any = False
            with self._engine.begin() as connection:
                ensure_relational_schema(connection)
                for product_id in missing:
                    product = products.get(product_id)
                    if product is None:
                        continue
                    if self._backfill_product(connection, product):
                        updated += 1
                        embedded_any = True
            if not embedded_any:
                break
        return updated

    def _missing_embedding_ids(self, batch_size: int) -> tuple[UUID, ...]:
        with self._engine.begin() as connection:
            ensure_relational_schema(connection)
            result = connection.execute(
                text(SELECT_MISSING_EMBEDDING_IDS_SQL),
                {"batch_size": batch_size},
            )
            return tuple(UUID(str(row["product_id"])) for row in result.mappings())

    def _backfill_product(self, connection: Connection, product: StoreProduct) -> bool:
        if self._embeddings is None:
            raise RuntimeError("embedding provider is required for store backfill")
        semantic_text = product_semantic_text(product)
        embedding = self._embeddings.embed(semantic_text, purpose="store-backfill")
        if embedding is None:
            return False
        result = connection.execute(
            text(UPDATE_PRODUCT_EMBEDDING_SQL),
            {
                "product_id": str(product.product_id),
                "embedding": vector_to_pg(embedding),
                "embedding_source_hash": semantic_hash(semantic_text),
            },
        )
        return bool(result.rowcount)


def _mapping_rows(result: Result[Any]) -> tuple[dict[str, Any], ...]:
    return tuple(dict(row) for row in result.mappings())
