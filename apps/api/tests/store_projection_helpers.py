from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

from coeus.core.config import Settings
from coeus.domain.access import ProductStatus
from coeus.domain.store import (
    StoreFacets,
    StoreHybridCandidate,
    StoreProduct,
    StoreProductSearchPage,
    StoreSearchFilters,
    StoreVisibilityScope,
)
from coeus.main import create_app
from coeus.repositories.access import SeedAccessRepository
from coeus.repositories.store import InMemoryStoreRepository


class RecordingProjection:
    def __init__(self, products: tuple[StoreProduct, ...] = ()) -> None:
        self.products = products
        self.leg_limits: list[int] = []
        self.saved_batches: list[tuple[StoreProduct, ...]] = []

    def list_products(self) -> tuple[StoreProduct, ...]:
        return self.products

    def search_product_page(
        self, filters: StoreSearchFilters, _scope: object
    ) -> StoreProductSearchPage:
        offset = (filters.page - 1) * filters.page_size
        products = self.products[offset : offset + filters.page_size]
        return StoreProductSearchPage(
            products=products,
            total=len(self.products),
            facets=StoreFacets(
                product_types=tuple(
                    sorted({product.metadata.product_type for product in self.products})
                ),
                regions=tuple(
                    sorted({product.metadata.area_or_region for product in self.products})
                ),
                tags=tuple(
                    sorted({tag for product in self.products for tag in product.metadata.tags})
                ),
            ),
        )

    def hybrid_candidates(
        self,
        _filters: object,
        _scope: object,
        _query: str,
        _query_embedding: tuple[float, ...] | None,
        _leg_limit: int = 50,
    ) -> tuple[StoreHybridCandidate, ...]:
        self.leg_limits.append(_leg_limit)
        return tuple(StoreHybridCandidate(product=product) for product in self.products)

    def get_visible_product(self, product_id: object, _scope: object) -> StoreProduct | None:
        for product in self.products:
            if str(product.product_id) == str(product_id):
                return product
        return None

    def save_product(self, product: StoreProduct) -> None:
        self.products = (product,)

    def save_products(self, products: tuple[StoreProduct, ...]) -> None:
        self.products = products
        self.saved_batches.append(products)

    def embedded_product_count(self) -> int:
        return len(self.products)

    def backfill_missing_embeddings(self, batch_size: int = 500) -> int:
        return min(len(self.products), batch_size)


class FakeEmbeddingService:
    """Records embed calls and returns a fixed 384-dimension retrieval vector."""

    def __init__(self, vector: tuple[float, ...] | None = (0.1,) * 384) -> None:
        self._vector = vector
        self.calls: list[tuple[str, str]] = []

    def embed(self, text: str, *, purpose: str) -> tuple[float, ...] | None:
        self.calls.append((text, purpose))
        return self._vector


class FakeSqlEngine:
    def __init__(
        self,
        products: tuple[StoreProduct, ...] = (),
        embedded: dict[str, str | None] | None = None,
    ) -> None:
        self.products = products
        self.statements: list[str] = []
        self.params: list[dict[str, Any]] = []
        # Maps product_id -> stored embedding_source_hash for products that
        # currently hold an embedding, mirroring the WHERE embedding IS NOT NULL rows.
        self.embedding_hashes: dict[str, str | None] = dict(embedded or {})

    def begin(self) -> FakeConnection:
        return FakeConnection(self)


class FakeConnection:
    def __init__(self, engine: FakeSqlEngine) -> None:
        self._engine = engine

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        return None

    def execute(self, statement: object, params: dict[str, Any] | None = None) -> FakeResult:
        sql = str(statement).strip()
        self._engine.statements.append(sql)
        if params is not None:
            self._engine.params.append(params)
        if sql.startswith("SELECT count(*)"):
            return FakeResult([{"count": len(self._engine.embedding_hashes)}])
        if sql.startswith("WITH filtered_products AS"):
            return FakeResult(
                [
                    {
                        "total": len(self._engine.products),
                        "product_types": sorted(
                            {product.metadata.product_type for product in self._engine.products}
                        ),
                        "regions": sorted(
                            {product.metadata.area_or_region for product in self._engine.products}
                        ),
                        "tags": sorted(
                            {
                                tag
                                for product in self._engine.products
                                for tag in product.metadata.tags
                            }
                        ),
                    }
                ]
            )
        if sql.startswith("SELECT product_id, embedding_source_hash"):
            requested = set(params.get("product_ids", []) if params else [])
            return FakeResult(
                [
                    {"product_id": pid, "embedding_source_hash": stored_hash}
                    for pid, stored_hash in self._engine.embedding_hashes.items()
                    if pid in requested
                ]
            )
        if sql.startswith("SELECT product_id") and "embedding IS NULL" in sql:
            batch_size = int(params.get("batch_size", len(self._engine.products)) if params else 0)
            missing = [
                {"product_id": product.product_id}
                for product in self._engine.products
                if str(product.product_id) not in self._engine.embedding_hashes
            ]
            return FakeResult(missing[:batch_size])
        if sql.startswith("UPDATE intelligence_store_products"):
            return self._update_embedding(params or {})
        if sql.startswith("INSERT INTO intelligence_store_products"):
            self._record_upsert(params or {})
            return FakeResult([])
        if sql.startswith("WITH scoped AS"):
            return FakeResult(
                [
                    _product_row(product)
                    | {
                        "lexical_rank": index + 1,
                        "lexical_score": 0.5,
                        "vector_rank": index + 1,
                        "vector_score": 0.8,
                    }
                    for index, product in enumerate(self._engine.products)
                ]
            )
        if sql.startswith("SELECT") and "intelligence_store_products" in sql:
            offset = int(params.get("offset", 0)) if params else 0
            page_size = (
                int(params.get("page_size", len(self._engine.products)))
                if params
                else len(self._engine.products)
            )
            products = self._engine.products[offset : offset + page_size]
            return FakeResult([_product_row(product) for product in products])
        if sql.startswith("SELECT") and "intelligence_store_assets" in sql:
            products = self._requested_products(params)
            return FakeResult([row for product in products for row in _asset_rows(product)])
        if sql.startswith("SELECT") and "intelligence_store_product_acgs" in sql:
            products = self._requested_products(params)
            return FakeResult([row for product in products for row in _acg_rows(product)])
        if sql.startswith("SELECT") and "intelligence_store_semantic_labels" in sql:
            products = self._requested_products(params)
            return FakeResult([row for product in products for row in _label_rows(product)])
        return FakeResult([])

    def _requested_products(self, params: dict[str, Any] | None) -> tuple[StoreProduct, ...]:
        if not params or "product_ids" not in params:
            return self._engine.products
        requested = set(params.get("product_ids", ()) if params else ())
        return tuple(
            product for product in self._engine.products if str(product.product_id) in requested
        )

    def _update_embedding(self, params: dict[str, Any]) -> FakeResult:
        product_id = params.get("product_id")
        if product_id is None or product_id in self._engine.embedding_hashes:
            return FakeResult([], rowcount=0)
        self._engine.embedding_hashes[str(product_id)] = params.get("embedding_source_hash")
        return FakeResult([], rowcount=1)

    def _record_upsert(self, params: dict[str, Any]) -> None:
        product_id = params.get("product_id")
        if product_id is None:
            return
        if params.get("embedding") is not None:
            self._engine.embedding_hashes[str(product_id)] = params.get("embedding_source_hash")


class FakeResult:
    def __init__(self, rows: list[dict[str, Any]], rowcount: int = 0) -> None:
        self._rows = rows
        self.rowcount = rowcount

    def mappings(self) -> FakeResult:
        return self

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self._rows)

    def first(self) -> tuple[object, ...] | None:
        if not self._rows:
            return None
        return tuple(self._rows[0].values())


def access_repository() -> SeedAccessRepository:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    return cast(SeedAccessRepository, app.state.access_services.repository)


def seed_product() -> StoreProduct:
    return InMemoryStoreRepository(access_repository()).list_products()[0]


def filters(query: str | None = None) -> StoreSearchFilters:
    return StoreSearchFilters(query=query)


def visibility_scope(product: StoreProduct) -> StoreVisibilityScope:
    return StoreVisibilityScope(
        acg_ids=product.metadata.acg_ids,
        clearance_level=product.metadata.classification_level,
        include_drafts=product.metadata.status == ProductStatus.DRAFT,
    )


def empty_visibility_scope() -> StoreVisibilityScope:
    return StoreVisibilityScope(acg_ids=frozenset(), clearance_level=5, include_drafts=True)


def _product_row(product: StoreProduct) -> dict[str, Any]:
    metadata = product.metadata
    bounding_box = metadata.bounding_box
    return {
        "product_id": product.product_id,
        "reference": product.reference,
        "title": metadata.title,
        "summary": metadata.summary,
        "description": metadata.description,
        "product_type": metadata.product_type,
        "source_type": metadata.source_type,
        "owner_team": metadata.owner_team,
        "area_or_region": metadata.area_or_region,
        "classification_level": metadata.classification_level,
        "releasability": sorted(metadata.releasability),
        "handling_caveats": sorted(metadata.handling_caveats),
        "tags": sorted(metadata.tags),
        "semantic_labels": sorted(metadata.semantic_labels),
        "acg_ids": sorted(metadata.acg_ids, key=str),
        "status": metadata.status.value,
        "time_period_start": metadata.time_period_start,
        "time_period_end": metadata.time_period_end,
        "geojson_ref": metadata.geojson_ref,
        "bounding_box": None
        if bounding_box is None
        else {
            "west": bounding_box.west,
            "south": bounding_box.south,
            "east": bounding_box.east,
            "north": bounding_box.north,
        },
        "created_by_user_id": product.created_by_user_id,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
    }


def _asset_rows(product: StoreProduct) -> list[dict[str, Any]]:
    return [
        {
            "asset_id": asset.asset_id,
            "product_id": product.product_id,
            "name": asset.name,
            "asset_type": asset.asset_type,
            "mime_type": asset.mime_type,
            "size_bytes": asset.size_bytes,
            "sha256": asset.sha256,
            "object_key": asset.object_key,
            "preview_kind": asset.preview_kind,
        }
        for asset in product.assets
    ]


def _acg_rows(product: StoreProduct) -> list[dict[str, Any]]:
    return [
        {"product_id": product.product_id, "acg_id": acg_id}
        for acg_id in sorted(product.metadata.acg_ids, key=str)
    ]


def _label_rows(product: StoreProduct) -> list[dict[str, Any]]:
    return [
        {"product_id": product.product_id, "label": label}
        for label in sorted(product.metadata.semantic_labels)
    ]
