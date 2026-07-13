from typing import Protocol
from uuid import UUID

from coeus.application.ports.embeddings import EmbeddingPort
from coeus.domain.store import (
    StoreHybridCandidate,
    StoreProduct,
    StoreProductSearchPage,
    StoreSearchFilters,
    StoreVisibilityScope,
    product_in_scope,
)
from coeus.persistence.codec import decode_value, encode_value
from coeus.persistence.state_store import StateStore
from coeus.repositories.access import AccessRepository
from coeus.repositories.store_hybrid import memory_hybrid_candidates
from coeus.repositories.store_ids import max_store_reference_counter
from coeus.repositories.store_projection import StoreProjection
from coeus.repositories.store_seed import STORE_SEED_REFERENCE_COUNTER, seed_store_products


class StoreRepository(Protocol):
    def list_products(self) -> tuple[StoreProduct, ...]: ...

    def search_product_page(
        self, filters: StoreSearchFilters, scope: StoreVisibilityScope
    ) -> StoreProductSearchPage | None: ...

    def hybrid_candidates(
        self,
        filters: StoreSearchFilters,
        scope: StoreVisibilityScope,
        query: str,
        query_embedding: tuple[float, ...] | None,
        leg_limit: int = 50,
    ) -> tuple[StoreHybridCandidate, ...]: ...

    def get_visible_product(
        self, product_id: UUID, scope: StoreVisibilityScope
    ) -> StoreProduct | None: ...

    def get_product(self, product_id: UUID) -> StoreProduct | None: ...

    def save_product(self, product: StoreProduct) -> None: ...

    def delete_product(self, product_id: UUID) -> None: ...

    def embedded_product_count(self) -> int: ...

    def backfill_missing_embeddings(self, batch_size: int = 500) -> int: ...

    def next_reference(self) -> str: ...

    def accept_committed(self, product: StoreProduct) -> None: ...


class InMemoryStoreRepository:
    def __init__(
        self,
        access_repository: AccessRepository,
        state_store: StateStore | None = None,
        projection: StoreProjection | None = None,
        embeddings: EmbeddingPort | None = None,
    ) -> None:
        self._access_repository = access_repository
        self._state_store = state_store
        self._projection = projection
        self._embeddings = embeddings
        self._initialising = True
        self._products: dict[UUID, StoreProduct] = {}
        self._reference_counter = 1000
        self._seed_products()
        self._initialising = False
        self._restore_or_persist()

    def list_products(self) -> tuple[StoreProduct, ...]:
        self._refresh_from_projection(allow_empty=True)
        return tuple(sorted(self._products.values(), key=lambda product: product.metadata.title))

    def search_product_page(
        self, filters: StoreSearchFilters, scope: StoreVisibilityScope
    ) -> StoreProductSearchPage | None:
        if self._projection is None:
            return None
        page = self._projection.search_product_page(filters, scope)
        self._products.update({product.product_id: product for product in page.products})
        return page

    def hybrid_candidates(
        self,
        filters: StoreSearchFilters,
        scope: StoreVisibilityScope,
        query: str,
        query_embedding: tuple[float, ...] | None,
        leg_limit: int = 50,
    ) -> tuple[StoreHybridCandidate, ...]:
        if self._projection is not None:
            candidates = self._projection.hybrid_candidates(
                filters,
                scope,
                query,
                query_embedding,
                leg_limit,
            )
            self._products.update(
                {candidate.product.product_id: candidate.product for candidate in candidates}
            )
            return candidates
        scoped = tuple(
            product for product in self.list_products() if product_in_scope(product, scope)
        )
        return memory_hybrid_candidates(
            scoped,
            query,
            query_embedding,
            self._embeddings,
            filters,
            leg_limit,
        )

    def get_visible_product(
        self, product_id: UUID, scope: StoreVisibilityScope
    ) -> StoreProduct | None:
        if self._projection is None:
            return self.get_product(product_id)
        product = self._projection.get_visible_product(product_id, scope)
        if product is not None:
            self._products[product.product_id] = product
        return product

    def get_product(self, product_id: UUID) -> StoreProduct | None:
        self._refresh_from_projection(allow_empty=True)
        return self._products.get(product_id)

    def save_product(self, product: StoreProduct) -> None:
        self._refresh_from_projection(allow_empty=True)
        products = dict(self._products)
        reference_counter = self._reference_counter
        self._products[product.product_id] = product
        try:
            self._persist()
        except Exception:
            self._products = products
            self._reference_counter = reference_counter
            raise

    def delete_product(self, product_id: UUID) -> None:
        """Remove a product, e.g. rolling back a failed QC approval."""
        self._refresh_from_projection(allow_empty=True)
        products = dict(self._products)
        reference_counter = self._reference_counter
        if self._products.pop(product_id, None) is not None:
            try:
                self._persist()
            except Exception:
                self._products = products
                self._reference_counter = reference_counter
                raise

    def embedded_product_count(self) -> int:
        if self._projection is None:
            return 0
        return self._projection.embedded_product_count()

    def backfill_missing_embeddings(self, batch_size: int = 500) -> int:
        if self._projection is None:
            return 0
        return self._projection.backfill_missing_embeddings(batch_size)

    def next_reference(self) -> str:
        self._refresh_from_projection(allow_empty=True)
        existing = {product.reference for product in self._products.values()}
        while True:
            self._reference_counter += 1
            reference = f"PROD-{self._reference_counter}"
            if reference not in existing:
                return reference

    def accept_committed(self, product: StoreProduct) -> None:
        """Update the cache after a transaction port has durably committed."""
        self._products[product.product_id] = product

    def _restore_or_persist(self) -> None:
        if self._restore_from_projection():
            self._persist_json_state()
            self._persist_projection()
            return
        if self._state_store is None:
            self._persist_projection()
            return
        payload = self._state_store.load("store")
        if payload is None:
            self._persist()
            return
        products = tuple(decode_value(item) for item in payload.get("products", []))
        self._products = {product.product_id: product for product in products}
        # Never let a regressed persisted counter re-issue an existing reference.
        self._reference_counter = max(
            int(payload.get("reference_counter", 1000)),
            max_store_reference_counter(products, 1000),
        )
        self._persist_projection()

    def _persist(self) -> None:
        if self._initialising:
            return
        self._persist_json_state()
        self._persist_projection()

    def _persist_json_state(self) -> None:
        if self._state_store is None:
            return
        products = sorted(self._products.values(), key=lambda product: product.metadata.title)
        self._state_store.save(
            "store",
            {
                "reference_counter": self._reference_counter,
                "products": [encode_value(product) for product in products],
            },
        )

    def _persist_projection(self) -> None:
        if self._projection is None:
            return
        products = tuple(
            sorted(self._products.values(), key=lambda product: product.metadata.title)
        )
        self._projection.save_products(products)

    def _restore_from_projection(self) -> bool:
        return self._refresh_from_projection(allow_empty=False)

    def _refresh_from_projection(self, *, allow_empty: bool) -> bool:
        if self._projection is None:
            return False
        products = self._projection.list_products()
        if not products and not allow_empty:
            return False
        self._products = {product.product_id: product for product in products}
        self._reference_counter = max_store_reference_counter(products, self._reference_counter)
        return True

    def _seed_products(self) -> None:
        products = seed_store_products(self._access_repository)
        self._products = {product.product_id: product for product in products}
        self._reference_counter = STORE_SEED_REFERENCE_COUNTER
