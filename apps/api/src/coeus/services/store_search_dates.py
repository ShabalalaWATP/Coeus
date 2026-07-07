from datetime import date

from coeus.domain.store import StoreProductMetadata


def _parse_date(value: str | None) -> date | None:
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
    """Check ISO date period overlap. Products without a period fail date filters.

    Values are compared as parsed dates, never lexicographically; invalid
    filter values are ignored and products with invalid periods are skipped.
    """
    lower = _parse_date(date_from)
    upper = _parse_date(date_to)
    if lower is None and upper is None:
        return True
    start = _parse_date(metadata.time_period_start)
    if start is None:
        return False
    end = _parse_date(metadata.time_period_end) or start
    if lower is not None and end < lower:
        return False
    return not (upper is not None and start > upper)
