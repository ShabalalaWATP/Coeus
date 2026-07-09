from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from uuid import uuid4

from coeus.persistence.state_store import StateStore


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    event_type: str
    occurred_at: datetime
    actor_user_id: str | None
    metadata: MappingProxyType[str, str]


class AuditLog:
    def __init__(self, max_events: int = 10_000, state_store: StateStore | None = None) -> None:
        if max_events < 1:
            raise ValueError("Audit log max_events must be at least 1.")
        self._max_events = max_events
        self._state_store = state_store
        self._events: list[AuditEvent] = []
        self._restore_or_persist()

    def record(
        self,
        event_type: str,
        actor_user_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            occurred_at=datetime.now(UTC),
            actor_user_id=actor_user_id,
            metadata=MappingProxyType(metadata or {}),
        )
        events = list(self._events)
        self._events.append(event)
        overflow = len(self._events) - self._max_events
        if overflow > 0:
            del self._events[:overflow]
        try:
            self._persist()
        except Exception:
            self._events = events
            raise
        return event

    def list_events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)

    def _restore_or_persist(self) -> None:
        if self._state_store is None:
            return
        payload = self._state_store.load("audit")
        if payload is None:
            self._persist()
            return
        self._events = [_event_from_payload(item) for item in payload.get("events", [])]

    def _persist(self) -> None:
        if self._state_store is None:
            return
        self._state_store.save(
            "audit",
            {"events": [_event_payload(event) for event in self._events[-self._max_events :]]},
        )


def _event_payload(event: AuditEvent) -> dict[str, object]:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "occurred_at": event.occurred_at.isoformat(),
        "actor_user_id": event.actor_user_id,
        "metadata": dict(event.metadata),
    }


def _event_from_payload(payload: object) -> AuditEvent:
    if not isinstance(payload, dict):
        raise ValueError("Audit event payload must be an object.")
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("Audit event metadata must be an object.")
    return AuditEvent(
        event_id=str(payload["event_id"]),
        event_type=str(payload["event_type"]),
        occurred_at=datetime.fromisoformat(str(payload["occurred_at"])),
        actor_user_id=payload["actor_user_id"] if payload["actor_user_id"] else None,
        metadata=MappingProxyType({str(key): str(value) for key, value in metadata.items()}),
    )
