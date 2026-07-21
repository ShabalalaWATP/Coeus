"""Application boundary for durable outbox claims and settlement."""

from typing import Protocol
from uuid import UUID

from coeus.domain.outbox import (
    FailureDisposition,
    OutboxMessage,
    OutboxStatus,
    ReplayDisposition,
)


class DispatchSummary(Protocol):
    @property
    def claimed(self) -> int: ...

    @property
    def delivered(self) -> int: ...

    @property
    def failed(self) -> int: ...

    @property
    def dead_lettered(self) -> int: ...


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
    ) -> FailureDisposition: ...

    def status(self) -> OutboxStatus: ...

    def replay_dead_letter(self, event_id: UUID) -> ReplayDisposition: ...


class OutboxDispatchPort(Protocol):
    def dispatch(self, worker_id: UUID, *, limit: int = 50) -> DispatchSummary: ...


class OutboxDispatcherPort(OutboxDispatchPort, Protocol):
    def status(self) -> OutboxStatus: ...

    def metrics_status(self) -> OutboxStatus | None: ...

    def replay_dead_letter(self, event_id: UUID) -> ReplayDisposition: ...
