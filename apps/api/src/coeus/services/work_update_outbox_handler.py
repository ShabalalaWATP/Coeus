"""Project only trusted, strict outbox messages into the work-update inbox."""

from coeus.application.ports.work_update_projection import WorkUpdateProjection
from coeus.domain.outbox import OutboxMessage
from coeus.domain.work_update_events import WORK_UPDATE_REQUESTED, WorkUpdateEvent


class WorkUpdateOutboxHandler:
    def __init__(self, projection: WorkUpdateProjection) -> None:
        self._projection = projection

    def __call__(self, message: OutboxMessage) -> None:
        if message.event_type != WORK_UPDATE_REQUESTED:
            raise ValueError("Unexpected outbox event type for a work update.")
        if message.aggregate_version < 1:
            raise ValueError("Work-update aggregate version is invalid.")
        event = WorkUpdateEvent.from_payload(message.payload)
        self._projection.project(message, event)
