"""Facet values and counts are derived in SQL, so they get the same recheck.

The SQL scope predicate and the service policy are independent implementations
of the same access rules. If they ever disagree, the projection is not trusted:
a product the requester cannot read must not contribute its region, type or tag
to the refinement options, nor be counted behind one.
"""

from dataclasses import replace
from uuid import uuid4

from coeus.domain.auth import UserAccount
from coeus.domain.store import StoreProduct, StoreSearchFilters
from coeus.repositories.store import InMemoryStoreRepository
from coeus.services.store import StoreSearchService
from coeus.services.store_product_policy import StoreProductAccessPolicy
from store_projection_helpers import RecordingProjection, access_repository, seed_product

HIDDEN_REGION = "Region only a hidden product covers"


def _catalogue() -> tuple[StoreProduct, ...]:
    base = seed_product()
    readable = replace(
        base,
        product_id=uuid4(),
        reference="PROD-FACET-1",
        metadata=replace(base.metadata, title="Readable product"),
    )
    # A classification above the actor's clearance is rejected by can_read but
    # is still returned here, standing in for any SQL/policy divergence.
    hidden = replace(
        base,
        product_id=uuid4(),
        reference="PROD-FACET-2",
        metadata=replace(
            base.metadata,
            title="Hidden product",
            area_or_region=HIDDEN_REGION,
            classification_level=5,
            tags=frozenset({"hidden-tag"}),
        ),
    )
    return (readable, hidden)


def _service() -> tuple[StoreSearchService, UserAccount]:
    access = access_repository()
    actor = access.get_user_by_username("user@example.test")
    assert actor is not None
    repository = InMemoryStoreRepository(access, projection=RecordingProjection(_catalogue()))
    return StoreSearchService(repository, StoreProductAccessPolicy(access)), actor


def test_a_hidden_product_never_appears_in_browse_facets() -> None:
    service, actor = _service()

    result = service.search(actor, StoreSearchFilters(product_type="assessment_report"))

    assert result.total == 0
    assert result.facets.regions == ()
    assert result.facets.tags == ()


def test_a_hidden_product_never_appears_in_facets_for_a_text_query() -> None:
    service, actor = _service()

    result = service.search(actor, StoreSearchFilters(query="product"))

    regions = {facet.value for facet in result.facets.regions}
    tags = {facet.value for facet in result.facets.tags}
    assert HIDDEN_REGION not in regions
    assert "hidden-tag" not in tags
    assert all(hit.product.metadata.area_or_region != HIDDEN_REGION for hit in result.hits)


def test_a_hidden_product_is_never_counted_behind_a_facet() -> None:
    service, actor = _service()

    result = service.search(actor, StoreSearchFilters(query="product"))

    assert sum(facet.count for facet in result.facets.product_types) == 0
