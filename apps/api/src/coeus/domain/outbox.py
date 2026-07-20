"""Durable workflow side-effect messages."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
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


class OutboxEventNotFound(LookupError):
    """Raised when an operator references an unknown outbox event."""


class FailureDisposition(StrEnum):
    RETRY_SCHEDULED = "retry_scheduled"
    DEAD_LETTERED = "dead_lettered"


class ReplayDisposition(StrEnum):
    REPLAYED = "replayed"
    ALREADY_PENDING = "already_pending"
    ALREADY_DELIVERED = "already_delivered"


@dataclass(frozen=True)
class OutboxStatus:
    pending_count: int
    retrying_count: int
    dead_letter_count: int
    oldest_pending_age_seconds: int | None
