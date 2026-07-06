from coeus.domain.store import StoreProductMetadata


def within_dates(
    metadata: StoreProductMetadata,
    date_from: str | None,
    date_to: str | None,
) -> bool:
    """Check ISO date period overlap. Products without a period fail date filters."""
    if date_from is None and date_to is None:
        return True
    start = metadata.time_period_start
    if start is None:
        return False
    end = metadata.time_period_end or start
    if date_from is not None and end < date_from:
        return False
    return not (date_to is not None and start > date_to)
