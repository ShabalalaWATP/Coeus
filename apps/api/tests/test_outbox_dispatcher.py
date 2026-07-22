from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from coeus.domain.outbox import (
    FailureDisposition,
    OutboxMessage,
    OutboxStatus,
    ReplayDisposition,
)
from coeus.services.outbox_dispatcher import DispatchResult, OutboxDispatcher


class MemoryOutbox:
    def __init__(self, messages: tuple[OutboxMessage, ...]) -> None:
        self.messages = messages
        self.delivered: list[UUID] = []
        self.failed: list[tuple[UUID, str]] = []
        self.status_calls = 0

    def claim_pending(
        self, _worker_id: UUID, *, limit: int, lease_seconds: int
    ) -> tuple[OutboxMessage, ...]:
        assert lease_seconds > 0
        return self.messages[:limit]

    def mark_delivered(self, event_id: UUID, _worker_id: UUID) -> None:
        self.delivered.append(event_id)

    def mark_failed(
        self,
        event_id: UUID,
        _worker_id: UUID,
        error: str,
        *,
        retry_seconds: int,
        max_attempts: int,
    ) -> FailureDisposition:
        assert retry_seconds > 0 and max_attempts > 0
        self.failed.append((event_id, error))
        message = next(item for item in self.messages if item.event_id == event_id)
        return (
            FailureDisposition.DEAD_LETTERED
            if message.attempt_count >= max_attempts
            else FailureDisposition.RETRY_SCHEDULED
        )

    def status(self) -> OutboxStatus:
        self.status_calls += 1
        return OutboxStatus(len(self.messages), 0, 0, 0)

    def replay_dead_letter(self, _event_id: UUID) -> ReplayDisposition:
        return ReplayDisposition.ALREADY_PENDING


def _message(event_type: str) -> OutboxMessage:
    return OutboxMessage(
        event_id=uuid4(),
        aggregate_id=uuid4(),
        aggregate_version=1,
        event_type=event_type,
        payload={"synthetic": True},
        created_at=datetime.now(UTC),
        attempt_count=1,
    )


def test_dispatcher_settles_success_and_retries_failures() -> None:
    success = _message("success")
    failure = _message("failure")
    unknown = _message("unknown")
    store = MemoryOutbox((success, failure, unknown))

    def fail(_message: OutboxMessage) -> None:
        raise RuntimeError("synthetic delivery failure")

    result = OutboxDispatcher(store, {"success": lambda _message: None, "failure": fail}).dispatch(
        uuid4()
    )

    assert result == DispatchResult(claimed=3, delivered=1, failed=2, dead_lettered=0)
    assert store.delivered == [success.event_id]
    assert [event_id for event_id, _error in store.failed] == [failure.event_id, unknown.event_id]
    assert "RuntimeError" in store.failed[0][1]
    assert "KeyError" in store.failed[1][1]


def test_dispatcher_counts_and_logs_poison_messages_without_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    poison = _message("poison")
    store = MemoryOutbox((poison,))
    logger = MagicMock()
    monkeypatch.setattr("coeus.services.outbox_dispatcher.logger", logger)

    def fail(_message: OutboxMessage) -> None:
        raise RuntimeError("sensitive synthetic payload")

    result = OutboxDispatcher(store, {"poison": fail}, max_attempts=1).dispatch(uuid4())

    assert result == DispatchResult(claimed=1, delivered=0, failed=1, dead_lettered=1)
    logger.error.assert_called_once_with(
        "outbox_message_dead_lettered",
        extra={
            "event_id": str(poison.event_id),
            "event_type": "poison",
            "attempt_count": poison.attempt_count,
        },
    )
    assert "sensitive synthetic payload" not in repr(logger.error.call_args)


def test_dispatch_refreshes_a_cached_metrics_snapshot_without_scrape_queries() -> None:
    store = MemoryOutbox(())
    dispatcher = OutboxDispatcher(store, {})

    assert dispatcher.metrics_status() is None
    dispatcher.dispatch(uuid4())

    assert dispatcher.metrics_status() == OutboxStatus(0, 0, 0, 0)
    assert dispatcher.metrics_status() == OutboxStatus(0, 0, 0, 0)
    assert store.status_calls == 1


def test_live_status_updates_the_cached_metrics_snapshot() -> None:
    store = MemoryOutbox((_message("pending"),))
    dispatcher = OutboxDispatcher(store, {})

    assert dispatcher.status() == OutboxStatus(1, 0, 0, 0)
    assert dispatcher.metrics_status() == OutboxStatus(1, 0, 0, 0)
    assert store.status_calls == 1


def test_metrics_refresh_is_rate_limited_and_failure_logs_no_exception_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = "synthetic private outbox status"
    store = MemoryOutbox(())
    store.status = MagicMock(side_effect=RuntimeError(sentinel))
    logger = MagicMock()
    monkeypatch.setattr("coeus.services.outbox_dispatcher.logger", logger)
    monkeypatch.setattr("coeus.services.outbox_dispatcher.monotonic", lambda: 10.0)
    dispatcher = OutboxDispatcher(store, {})

    dispatcher.dispatch(uuid4())
    dispatcher.dispatch(uuid4())

    assert store.status.call_count == 1
    assert dispatcher.metrics_status() is None
    logger.warning.assert_called_once_with("outbox_metrics_refresh_failed")
    assert sentinel not in repr(logger.mock_calls)


def test_metrics_refresh_is_single_flight() -> None:
    store = MemoryOutbox(())
    entered = Event()
    release = Event()

    def slow_status() -> OutboxStatus:
        store.status_calls += 1
        entered.set()
        assert release.wait(timeout=5)
        return OutboxStatus(0, 0, 0, None)

    store.status = slow_status
    dispatcher = OutboxDispatcher(store, {})
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(dispatcher.dispatch, uuid4())
        assert entered.wait(timeout=5)
        second = pool.submit(dispatcher.dispatch, uuid4())
        second.result(timeout=5)
        release.set()
        first.result(timeout=5)

    assert store.status_calls == 1
    assert dispatcher.metrics_status() == OutboxStatus(0, 0, 0, None)
