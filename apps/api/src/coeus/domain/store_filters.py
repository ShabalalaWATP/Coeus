from coeus.domain.store import StoreProduct, StoreSearchFilters
from coeus.domain.store_dates import within_dates


def structured_filter_match(product: StoreProduct, filters: StoreSearchFilters) -> bool:
    metadata = product.metadata
    return all(
        (
            filters.product_type is None or metadata.product_type == filters.product_type,
            _contains(metadata.area_or_region, filters.region),
            filters.tag is None
            or filters.tag.casefold() in {tag.casefold() for tag in metadata.tags},
            filters.source_type is None or metadata.source_type == filters.source_type,
            filters.status is None or metadata.status == filters.status,
            filters.project_id is None or metadata.project_id == filters.project_id,
            within_dates(metadata, filters.date_from, filters.date_to),
            filters.owner_team is None
            or metadata.owner_team.casefold() == filters.owner_team.casefold(),
        )
    )


def _contains(value: str, needle: str | None) -> bool:
    return needle is None or needle.casefold() in value.casefold()
