"""Shared routing endpoint precondition contracts."""

from datetime import datetime
from typing import Any

from coeus.core.errors import AppError
from coeus.schemas.routing import RoutingErrorResponse

VERSION_REQUIRED_RESPONSE: dict[int | str, dict[str, Any]] = {
    428: {
        "model": RoutingErrorResponse,
        "description": "The expected ticket version is required before this decision.",
    }
}


def required_version(value: datetime | None) -> datetime:
    """Require the caller to act on the ticket version it displayed."""
    if value is None:
        raise AppError(
            428,
            "ticket_version_required",
            "Refresh the ticket before submitting this decision.",
        )
    return value
