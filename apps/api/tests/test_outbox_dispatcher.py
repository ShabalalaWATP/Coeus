from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.domain.outbox import OutboxMessage
from coeus.services.outbox_dispatcher import DispatchResult, OutboxDispatcher


class MemoryOutbox:
    def __init__(self, messages: tuple[OutboxMessage, ...]) -> None:
        self.messages = messages
        self.delivered: list[UUID] = []
        self.failed: list[tuple[UUID, str]] = []

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
    ) -> None:
        assert retry_seconds > 0 and max_attempts > 0
        self.failed.append((event_id, error))


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

    assert result == DispatchResult(claimed=3, delivered=1, failed=2)
    assert store.delivered == [success.event_id]
    assert [event_id for event_id, _error in store.failed] == [failure.event_id, unknown.event_id]
    assert "RuntimeError" in store.failed[0][1]
    assert "KeyError" in store.failed[1][1]
