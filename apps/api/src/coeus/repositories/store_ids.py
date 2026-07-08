from uuid import UUID, uuid4


def new_store_product_id() -> UUID:
    return uuid4()
