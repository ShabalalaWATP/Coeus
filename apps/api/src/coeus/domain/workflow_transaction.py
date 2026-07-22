"""Persistence-neutral intents committed with a workflow transition."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID


@dataclass(frozen=True)
class WorkflowAuditIntent:
    event_type: str
    actor_user_id: UUID
    metadata: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class WorkflowOutboxIntent:
    event_type: str
    payload: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.event_type or len(self.event_type) > 80:
            raise ValueError("Workflow outbox event type is invalid.")
        payload = dict(self.payload)
        if not payload or len(payload) > 16:
            raise ValueError("Workflow outbox payload is invalid.")
        if any(
            not isinstance(key, str)
            or not key
            or len(key) > 80
            or not isinstance(value, str)
            or not value
            or len(value) > 200
            for key, value in payload.items()
        ):
            raise ValueError("Workflow outbox payload values are invalid.")
        object.__setattr__(self, "payload", MappingProxyType(payload))


@dataclass(frozen=True)
class ReleaseNotificationIntent:
    requester_user_id: UUID
    ticket_reference: str
    product_id: UUID
    product_reference: str
    product_title: str
