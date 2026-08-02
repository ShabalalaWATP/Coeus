"""User-safe errors for retained-ticket admission denials."""

from coeus.core.errors import AppError


def ticket_capacity_error(denial_scope: str) -> AppError:
    """Describe principal limits accurately without exposing deployment internals."""
    if denial_scope == "principal":
        return AppError(
            429,
            "ticket_capacity_exhausted",
            "You have reached the active request limit. Close or cancel an existing request "
            "before opening another.",
        )
    return AppError(
        429,
        "ticket_capacity_exhausted",
        "Ticket capacity is temporarily unavailable.",
    )
