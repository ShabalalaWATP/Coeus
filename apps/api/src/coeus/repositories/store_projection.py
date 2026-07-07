from typing import Protocol
from uuid import UUID

from coeus.domain.store import StoreProduct, StoreSearchFilters, StoreVisibilityScope


class StoreProjection(Protocol):
    def list_products(self) -> tuple[StoreProduct, ...]:
        raise NotImplementedError

    def search_products(
        self, filters: StoreSearchFilters, scope: StoreVisibilityScope
    ) -> tuple[StoreProduct, ...]:
        raise NotImplementedError

    def get_visible_product(
        self, product_id: UUID, scope: StoreVisibilityScope
    ) -> StoreProduct | None:
        raise NotImplementedError

    def save_product(self, product: StoreProduct) -> None:
        raise NotImplementedError

    def save_products(self, products: tuple[StoreProduct, ...]) -> None:
        raise NotImplementedError
