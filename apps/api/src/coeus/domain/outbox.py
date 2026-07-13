"""Durable workflow side-effect messages."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class OutboxMessage:
    event_id: UUID
    aggregate_id: UUID
    aggregate_version: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime
    attempt_count: int


class OutboxClaimLost(RuntimeError):
    """Raised when a stale worker attempts to settle a claimed message."""
