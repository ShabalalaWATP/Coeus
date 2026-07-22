from coeus.core.errors import AppError
from coeus.core.resource_limits import MAX_STORE_RESULT_WINDOW
from coeus.domain.store import StoreSearchFilters


def require_bounded_result_window(filters: StoreSearchFilters) -> None:
    """Reject caller-selected Store windows that exceed the database work budget."""
    offset = (filters.page - 1) * filters.page_size
    if offset >= MAX_STORE_RESULT_WINDOW:
        raise AppError(
            422,
            "store_result_window_exceeded",
            "Choose narrower filters or restart from an earlier page.",
        )
