from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID


@dataclass(frozen=True)
class DomainEvent:
    event_type: str
    aggregate_id: UUID
    occurred_at: datetime

    @classmethod
    def create(cls, event_type: str, aggregate_id: UUID) -> "DomainEvent":
        return cls(event_type=event_type, aggregate_id=aggregate_id, occurred_at=datetime.now(UTC))
