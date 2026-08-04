"""Trusted, transaction-local producer for privacy-minimised work updates."""

import json
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.work_update_events import WORK_UPDATE_REQUESTED, WorkUpdateEvent


def append_work_update_request(
    connection: Connection,
    *,
    causation_id: UUID,
    aggregate_version: int,
    actor_user_id: UUID,
    event: WorkUpdateEvent,
    occurred_at: datetime,
) -> UUID:
    """Append one strictly generated request beside its source mutation."""
    if aggregate_version < 1:
        raise ValueError("work-update aggregate version must be positive")
    event_id = uuid5(
        NAMESPACE_URL,
        f"coeus:work-update-request:{causation_id}:{event.recipient_user_id}:{event.kind.value}",
    )
    aggregate_id = uuid5(event_id, "work-update-projection")
    payload = json.dumps(event.to_payload(), separators=(",", ":"), sort_keys=True)
    values = {
        "event_id": event_id,
        "aggregate_id": aggregate_id,
        "version": aggregate_version,
        "event_type": WORK_UPDATE_REQUESTED,
        "payload": payload,
        "actor": actor_user_id,
        "occurred_at": occurred_at,
    }
    connection.execute(
        text(
            "INSERT INTO coeus_audit_events"
            "(event_id,event_type,occurred_at,actor_user_id,metadata) "
            "VALUES (:event_id,:event_type,:occurred_at,:actor,CAST(:payload AS jsonb)) "
            "ON CONFLICT(event_id) DO NOTHING"
        ),
        values,
    )
    connection.execute(
        text(
            "INSERT INTO coeus_outbox"
            "(event_id,aggregate_id,aggregate_version,event_type,payload) "
            "VALUES (:event_id,:aggregate_id,:version,:event_type,CAST(:payload AS jsonb)) "
            "ON CONFLICT(aggregate_id,aggregate_version,event_type) DO NOTHING"
        ),
        values,
    )
    return event_id
