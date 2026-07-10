from dataclasses import replace
from uuid import uuid4

from coeus.domain.store import StoreProduct
from coeus.repositories.store import InMemoryStoreRepository
from coeus.repositories.store_hybrid import memory_hybrid_candidates
from coeus.services.store import StoreSearchService
from coeus.services.store_product_policy import StoreProductAccessPolicy
from store_projection_helpers import (
    RecordingProjection,
    access_repository,
    filters,
    seed_product,
)


def test_rfi_default_memory_hybrid_window_stays_pinned_to_fifty() -> None:
    products = _ranked_products(60)
    target = products[-1]

    candidates = memory_hybrid_candidates(products, "vessel", None)

    assert len(candidates) == 50
    assert target.product_id not in {candidate.product.product_id for candidate in candidates}


def test_store_browse_memory_hybrid_window_reaches_beyond_fifty() -> None:
    products = _ranked_products(60)
    target = products[-1]

    candidates = memory_hybrid_candidates(products, "vessel", None, leg_limit=500)

    assert len(candidates) == 60
    assert target.product_id in {candidate.product.product_id for candidate in candidates}


def test_store_service_passes_browse_limit_and_rfi_default_limit() -> None:
    access_repo = access_repository()
    admin = access_repo.get_user_by_username("admin@example.test")
    assert admin is not None
    product = seed_product()
    projection = RecordingProjection((product,))
    repository = InMemoryStoreRepository(access_repo, projection=projection)
    service = StoreSearchService(repository, StoreProductAccessPolicy(access_repo))

    service.hybrid_candidates(admin, filters(query="assessment"), "assessment", None)
    service.search(admin, filters(query="assessment"))

    assert projection.leg_limits[0] == 50
    assert projection.leg_limits[-1] == 500


def _ranked_products(count: int) -> tuple[StoreProduct, ...]:
    product = seed_product()
    return tuple(
        replace(
            product,
            product_id=uuid4(),
            reference=f"PROD-RANK-{index:03d}",
            metadata=replace(
                product.metadata,
                title=f"Vessel Fixture {index:03d}",
                summary="MOCK DATA ONLY vessel browse ranking fixture.",
                semantic_labels=frozenset(),
            ),
        )
        for index in range(1, count + 1)
    )
