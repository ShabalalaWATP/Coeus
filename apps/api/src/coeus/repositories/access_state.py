from dataclasses import dataclass
from uuid import UUID

from coeus.domain.access import (
    AccessControlGroup,
    AccessControlGroupMembership,
    ProductRecord,
)
from coeus.persistence.codec import decode_value, encode_value
from coeus.persistence.state_store import StateStore


@dataclass(frozen=True)
class AccessSnapshot:
    acgs: dict[UUID, AccessControlGroup]
    memberships: set[AccessControlGroupMembership]
    products: dict[UUID, ProductRecord]


def load_access_snapshot(state_store: StateStore) -> AccessSnapshot | None:
    payload = state_store.load("access")
    if payload is None:
        return None
    acgs = tuple(decode_value(item) for item in payload.get("acgs", []))
    memberships = tuple(decode_value(item) for item in payload.get("memberships", []))
    products = tuple(decode_value(item) for item in payload.get("products", []))
    return AccessSnapshot(
        acgs={acg.acg_id: acg for acg in acgs},
        memberships=set(memberships),
        products={product.product_id: product for product in products},
    )


def save_access_snapshot(
    state_store: StateStore,
    acgs: tuple[AccessControlGroup, ...],
    memberships: set[AccessControlGroupMembership],
    products: dict[UUID, ProductRecord],
) -> None:
    state_store.save(
        "access",
        {
            "acgs": [encode_value(acg) for acg in acgs],
            "memberships": [encode_value(item) for item in sorted(memberships, key=str)],
            "products": [
                encode_value(product)
                for product in sorted(products.values(), key=lambda item: item.title)
            ],
        },
    )
