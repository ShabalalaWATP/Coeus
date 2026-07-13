"""Persistence-neutral intents committed with a workflow transition."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class WorkflowAuditIntent:
    event_type: str
    actor_user_id: UUID
    metadata: dict[str, str]


@dataclass(frozen=True)
class ReleaseNotificationIntent:
    requester_user_id: UUID
    ticket_reference: str
    product_id: UUID
    product_reference: str
    product_title: str
