from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from uuid import uuid4


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    event_type: str
    occurred_at: datetime
    actor_user_id: str | None
    metadata: MappingProxyType[str, str]


class AuditLog:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

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
        self._events.append(event)
        return event

    def list_events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)
