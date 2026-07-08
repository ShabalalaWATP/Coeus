from typing import Protocol
from uuid import UUID

from coeus.domain.store import (
    StoreHybridCandidate,
    StoreProduct,
    StoreSearchFilters,
    StoreVisibilityScope,
)


class StoreProjection(Protocol):
    def list_products(self) -> tuple[StoreProduct, ...]:
        raise NotImplementedError

    def search_products(
        self, filters: StoreSearchFilters, scope: StoreVisibilityScope
    ) -> tuple[StoreProduct, ...]:
        raise NotImplementedError

    def hybrid_candidates(
        self,
        filters: StoreSearchFilters,
        scope: StoreVisibilityScope,
        query: str,
        query_embedding: tuple[float, ...] | None,
    ) -> tuple[StoreHybridCandidate, ...]:
        raise NotImplementedError

    def get_visible_product(
        self, product_id: UUID, scope: StoreVisibilityScope
    ) -> StoreProduct | None:
        raise NotImplementedError

    def save_product(self, product: StoreProduct) -> None:
        raise NotImplementedError

    def save_products(self, products: tuple[StoreProduct, ...]) -> None:
        raise NotImplementedError

    def embedded_product_count(self) -> int:
        raise NotImplementedError

    def backfill_missing_embeddings(self, batch_size: int = 500) -> int:
        raise NotImplementedError
