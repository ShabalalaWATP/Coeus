from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from types import MappingProxyType
from uuid import uuid4

from coeus.persistence.audit_store import AuditEventStore, MemoryAuditEventStore


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    event_type: str
    occurred_at: datetime
    actor_user_id: str | None
    metadata: MappingProxyType[str, str]


@dataclass(frozen=True)
class AuditEventPage:
    events: tuple[AuditEvent, ...]
    next_cursor: str | None


class AuditLog:
    def __init__(
        self,
        max_events: int = 10_000,
        event_store: AuditEventStore | None = None,
    ) -> None:
        if max_events < 1:
            raise ValueError("Audit log max_events must be at least 1.")
        self._max_events = max_events
        self._event_store = event_store or MemoryAuditEventStore()
        self._lock = RLock()
        self._events = list(self.list_page(max_events).events)

    def record(
        self,
        event_type: str,
        actor_user_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> AuditEvent:
        with self._lock:
            event = AuditEvent(
                event_id=str(uuid4()),
                event_type=event_type,
                occurred_at=datetime.now(UTC),
                actor_user_id=actor_user_id,
                metadata=MappingProxyType(dict(metadata or {})),
            )
            self._event_store.append(_event_payload(event))
            self._events.append(event)
            self._events = self._events[-self._max_events :]
            return event

    def record_many(
        self,
        events: tuple[tuple[str, str | None, dict[str, str]], ...],
    ) -> tuple[AuditEvent, ...]:
        """Append a group atomically, or leave both the store and cache unchanged."""
        if not events:
            raise ValueError("Audit event batch must not be empty.")
        with self._lock:
            prepared = tuple(
                AuditEvent(
                    event_id=str(uuid4()),
                    event_type=event_type,
                    occurred_at=datetime.now(UTC),
                    actor_user_id=actor_user_id,
                    metadata=MappingProxyType(dict(metadata)),
                )
                for event_type, actor_user_id, metadata in events
            )
            self._event_store.append_many(tuple(_event_payload(event) for event in prepared))
            self._events.extend(prepared)
            self._events = self._events[-self._max_events :]
            return prepared

    def list_events(self) -> tuple[AuditEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def refresh_from_store(self) -> None:
        """Refresh the bounded cache after an external transaction commits."""
        with self._lock:
            self._events = list(self.list_page(self._max_events).events)

    def list_page(self, limit: int, before_event_id: str | None = None) -> AuditEventPage:
        if limit < 1:
            raise ValueError("Audit page limit must be at least 1.")
        with self._lock:
            stored = self._event_store.list_page(limit, before_event_id)
            return AuditEventPage(
                events=tuple(_event_from_payload(item) for item in stored.events),
                next_cursor=stored.next_cursor,
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
