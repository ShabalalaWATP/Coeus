from uuid import UUID, uuid4

from coeus.domain.store import StoreProduct


def new_store_product_id() -> UUID:
    return uuid4()


def max_store_reference_counter(products: tuple[StoreProduct, ...], default: int) -> int:
    counter = default
    for product in products:
        prefix, _, suffix = product.reference.partition("-")
        if prefix == "PROD" and suffix.isdigit():
            counter = max(counter, int(suffix))
    return counter
