"""Bounded, retry-safe delivery of durable workflow side effects."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from uuid import UUID

from coeus.application.ports.outbox import OutboxStore
from coeus.core.logging import get_logger
from coeus.domain.outbox import (
    FailureDisposition,
    OutboxMessage,
    OutboxStatus,
    ReplayDisposition,
)

OutboxHandler = Callable[[OutboxMessage], None]
logger = get_logger(__name__)
METRICS_REFRESH_SECONDS = 30.0


@dataclass(frozen=True)
class DispatchResult:
    claimed: int
    delivered: int
    failed: int
    dead_lettered: int


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
        self._metrics_lock = Lock()
        self._metrics_snapshot: OutboxStatus | None = None
        self._metrics_refreshing = False
        self._metrics_last_attempt = float("-inf")

    def dispatch(self, worker_id: UUID, *, limit: int = 50) -> DispatchResult:
        messages = self._store.claim_pending(
            worker_id, limit=limit, lease_seconds=self._lease_seconds
        )
        delivered = 0
        failed = 0
        dead_lettered = 0
        for message in messages:
            try:
                handler = self._handlers[message.event_type]
                handler(message)
            except Exception as exc:
                disposition = self._store.mark_failed(
                    message.event_id,
                    worker_id,
                    f"{type(exc).__name__}: {exc}",
                    retry_seconds=self._retry_seconds,
                    max_attempts=self._max_attempts,
                )
                failed += 1
                if disposition == FailureDisposition.DEAD_LETTERED:
                    dead_lettered += 1
                    logger.error(
                        "outbox_message_dead_lettered",
                        extra={
                            "event_id": str(message.event_id),
                            "event_type": message.event_type,
                            "attempt_count": message.attempt_count,
                        },
                    )
            else:
                self._store.mark_delivered(message.event_id, worker_id)
                delivered += 1
        result = DispatchResult(len(messages), delivered, failed, dead_lettered)
        self._refresh_metrics_status_if_due()
        return result

    def status(self) -> OutboxStatus:
        status = self._store.status()
        self._cache_metrics_status(status)
        return status

    def metrics_status(self) -> OutboxStatus | None:
        """Return the last bounded background snapshot without database work."""
        with self._metrics_lock:
            return self._metrics_snapshot

    def replay_dead_letter(self, event_id: UUID) -> ReplayDisposition:
        return self._store.replay_dead_letter(event_id)

    def _refresh_metrics_status_if_due(self) -> None:
        now = monotonic()
        with self._metrics_lock:
            if (
                self._metrics_refreshing
                or now - self._metrics_last_attempt < METRICS_REFRESH_SECONDS
            ):
                return
            self._metrics_refreshing = True
            self._metrics_last_attempt = now
        try:
            status = self._store.status()
        except Exception:
            logger.warning("outbox_metrics_refresh_failed")
        else:
            self._cache_metrics_status(status)
        finally:
            with self._metrics_lock:
                self._metrics_refreshing = False

    def _cache_metrics_status(self, status: OutboxStatus) -> None:
        with self._metrics_lock:
            self._metrics_snapshot = status
