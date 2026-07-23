"""Pure construction of synthetic Access-repository products."""

from uuid import UUID

from coeus.domain.access import ProductRecord, ProductStatus


def build_seed_product(
    product_id: UUID,
    title: str,
    summary: str,
    product_type: str,
    status: ProductStatus,
    classification_level: int,
    handling_caveats: frozenset[str],
    acg_ids: frozenset[UUID],
    owner_team: str,
) -> ProductRecord:
    return ProductRecord(
        product_id=product_id,
        title=title,
        summary=summary,
        product_type=product_type,
        status=status,
        classification_level=classification_level,
        handling_caveats=handling_caveats,
        acg_ids=acg_ids,
        owner_team=owner_team,
    )
