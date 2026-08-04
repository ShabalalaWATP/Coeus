"""Trusted projection boundary for durable work-update events."""

from typing import Protocol

from coeus.domain.outbox import OutboxMessage
from coeus.domain.work_update_events import WorkUpdateEvent


class WorkUpdateProjection(Protocol):
    def project(self, message: OutboxMessage, event: WorkUpdateEvent) -> bool: ...
