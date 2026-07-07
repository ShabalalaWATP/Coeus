from typing import Protocol
from uuid import UUID

from coeus.domain.store import StoreProduct, StoreSearchFilters, StoreVisibilityScope


class StoreProjection(Protocol):
    def list_products(self) -> tuple[StoreProduct, ...]: ...

    def search_products(
        self, filters: StoreSearchFilters, scope: StoreVisibilityScope
    ) -> tuple[StoreProduct, ...]: ...

    def get_visible_product(
        self, product_id: UUID, scope: StoreVisibilityScope
    ) -> StoreProduct | None: ...

    def save_product(self, product: StoreProduct) -> None: ...

    def save_products(self, products: tuple[StoreProduct, ...]) -> None: ...
