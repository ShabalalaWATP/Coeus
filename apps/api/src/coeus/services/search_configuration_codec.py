"""Safe scalar codecs for persisted search administration state."""

from datetime import datetime
from typing import Literal, cast

SearchIndexStatus = Literal["ready", "stale", "indexing", "degraded", "failed"]


def search_index_status(value: object) -> SearchIndexStatus:
    if value in {"ready", "stale", "indexing", "degraded", "failed"}:
        return cast(SearchIndexStatus, value)
    return "stale"


def optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def optional_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def encode_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
