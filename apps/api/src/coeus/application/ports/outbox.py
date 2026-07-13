"""Application boundary for durable outbox claims and settlement."""

from typing import Protocol
from uuid import UUID

from coeus.domain.outbox import OutboxMessage


class DispatchSummary(Protocol):
    claimed: int
    delivered: int
    failed: int


class OutboxStore(Protocol):
    def claim_pending(
        self, worker_id: UUID, *, limit: int, lease_seconds: int
    ) -> tuple[OutboxMessage, ...]: ...

    def mark_delivered(self, event_id: UUID, worker_id: UUID) -> None: ...

    def mark_failed(
        self,
        event_id: UUID,
        worker_id: UUID,
        error: str,
        *,
        retry_seconds: int,
        max_attempts: int,
    ) -> None: ...


class OutboxDispatcherPort(Protocol):
    def dispatch(self, worker_id: UUID, *, limit: int = 50) -> DispatchSummary: ...
