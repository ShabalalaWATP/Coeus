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
class ReleaseNotificationIntent:
    requester_user_id: UUID
    ticket_reference: str
    product_id: UUID
    product_reference: str
    product_title: str
