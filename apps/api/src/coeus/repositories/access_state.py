from dataclasses import dataclass
from uuid import UUID

from coeus.domain.access import (
    AccessControlGroup,
    AccessControlGroupMembership,
    ProductRecord,
    ProjectWorkspace,
)
from coeus.persistence.codec import decode_value, encode_value
from coeus.persistence.state_store import StateStore


@dataclass(frozen=True)
class AccessSnapshot:
    acgs: dict[UUID, AccessControlGroup]
    memberships: set[AccessControlGroupMembership]
    products: dict[UUID, ProductRecord]
    projects: dict[UUID, ProjectWorkspace]


def load_access_snapshot(state_store: StateStore) -> AccessSnapshot | None:
    payload = state_store.load("access")
    if payload is None:
        return None
    acgs = tuple(decode_value(item) for item in payload.get("acgs", []))
    memberships = tuple(decode_value(item) for item in payload.get("memberships", []))
    products = tuple(decode_value(item) for item in payload.get("products", []))
    projects = tuple(decode_value(item) for item in payload.get("projects", []))
    return AccessSnapshot(
        acgs={acg.acg_id: acg for acg in acgs},
        memberships=set(memberships),
        products={product.product_id: product for product in products},
        projects={project.project_id: project for project in projects},
    )


def save_access_snapshot(
    state_store: StateStore,
    acgs: tuple[AccessControlGroup, ...],
    memberships: set[AccessControlGroupMembership],
    products: dict[UUID, ProductRecord],
    projects: dict[UUID, ProjectWorkspace],
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
            "projects": [
                encode_value(project)
                for project in sorted(projects.values(), key=lambda item: item.reference)
            ],
        },
    )
