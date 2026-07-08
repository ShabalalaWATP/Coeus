from datetime import date

from coeus.domain.store import StoreProductMetadata


def parse_date(value: str | None) -> date | None:
    """Parse an ISO calendar date, treating invalid values as absent."""
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def within_dates(
    metadata: StoreProductMetadata,
    date_from: str | None,
    date_to: str | None,
) -> bool:
    """Check ISO date period overlap. Products without a period fail date filters."""
    lower = parse_date(date_from)
    upper = parse_date(date_to)
    if lower is None and upper is None:
        return True
    start = parse_date(metadata.time_period_start)
    if start is None:
        return False
    end = parse_date(metadata.time_period_end) or start
    if lower is not None and end < lower:
        return False
    return not (upper is not None and start > upper)
