"""Bounded, retry-safe delivery of durable workflow side effects."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from uuid import UUID

from coeus.application.ports.outbox import OutboxStore
from coeus.domain.outbox import OutboxMessage

OutboxHandler = Callable[[OutboxMessage], None]


@dataclass(frozen=True)
class DispatchResult:
    claimed: int
    delivered: int
    failed: int


class OutboxDispatcher:
    def __init__(
        self,
        store: OutboxStore,
        handlers: Mapping[str, OutboxHandler],
        *,
        lease_seconds: int = 60,
        retry_seconds: int = 30,
        max_attempts: int = 5,
    ) -> None:
        self._store = store
        self._handlers = dict(handlers)
        self._lease_seconds = lease_seconds
        self._retry_seconds = retry_seconds
        self._max_attempts = max_attempts

    def dispatch(self, worker_id: UUID, *, limit: int = 50) -> DispatchResult:
        messages = self._store.claim_pending(
            worker_id, limit=limit, lease_seconds=self._lease_seconds
        )
        delivered = 0
        failed = 0
        for message in messages:
            try:
                handler = self._handlers[message.event_type]
                handler(message)
            except Exception as exc:
                self._store.mark_failed(
                    message.event_id,
                    worker_id,
                    f"{type(exc).__name__}: {exc}",
                    retry_seconds=self._retry_seconds,
                    max_attempts=self._max_attempts,
                )
                failed += 1
            else:
                self._store.mark_delivered(message.event_id, worker_id)
                delivered += 1
        return DispatchResult(len(messages), delivered, failed)
