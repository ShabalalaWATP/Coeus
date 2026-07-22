"""Persisted customer-safe snapshots of matching active work."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ActiveWorkOffer:
    ticket_id: UUID
    reference: str
    title: str
    state: str
    score: float
    reasons: tuple[str, ...]
    request_kind: str
    approved_route: str | None
    assigned_team: str | None
    requesting_unit: str | None
    supported_operation: str | None
    time_period_start: str | None
    time_period_end: str | None
    status: str
    created_at: datetime
    decided_at: datetime | None = None
