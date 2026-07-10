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
        pass

    def search_products(
        self, filters: StoreSearchFilters, scope: StoreVisibilityScope
    ) -> tuple[StoreProduct, ...]:
        pass

    def hybrid_candidates(
        self,
        filters: StoreSearchFilters,
        scope: StoreVisibilityScope,
        query: str,
        query_embedding: tuple[float, ...] | None,
        leg_limit: int = 50,
    ) -> tuple[StoreHybridCandidate, ...]:
        pass

    def get_visible_product(
        self, product_id: UUID, scope: StoreVisibilityScope
    ) -> StoreProduct | None:
        pass

    def save_product(self, product: StoreProduct) -> None:
        pass

    def save_products(self, products: tuple[StoreProduct, ...]) -> None:
        pass

    def embedded_product_count(self) -> int:
        pass

    def backfill_missing_embeddings(self, batch_size: int = 500) -> int:
        pass
