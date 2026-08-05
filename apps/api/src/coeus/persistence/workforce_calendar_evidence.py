"""Bounded audit and outbox evidence for calendar mutations."""

import json
from datetime import datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.workforce_calendar import CalendarMutationCommand, CalendarMutationResult


def append_calendar_evidence(
    connection: Connection,
    command: CalendarMutationCommand,
    result: CalendarMutationResult,
    occurred_at: datetime,
) -> None:
    suffix = {
        "create": "created",
        "update": "updated",
        "cancel": "cancelled",
        "update_occurrence": "occurrence_updated",
        "cancel_occurrence": "occurrence_cancelled",
        "update_future": "future_split",
    }[command.request.operation.value]
    event_type = f"calendar_event_{suffix}"
    event_id = uuid5(NAMESPACE_URL, f"coeus:{event_type}:{command.command_id}")
    payload = json.dumps(
        {
            "event_id": str(result.event_id),
            "owner_user_id": str(command.request.event.owner_user_id),
            "source": command.request.event.source.value,
            "version": result.version,
            "reason_hash": sha256(command.request.reason.encode()).hexdigest(),
            "occurrence_key": command.request.occurrence_key,
            "future_event_id": (
                None if result.future_event_id is None else str(result.future_event_id)
            ),
        },
        sort_keys=True,
    )
    values = {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": occurred_at,
        "actor_user_id": str(command.actor_user_id),
        "aggregate_id": result.event_id,
        "result_version": result.version,
        "payload": payload,
    }
    connection.execute(
        text(
            "INSERT INTO coeus_audit_events"
            "(event_id,event_type,occurred_at,actor_user_id,metadata) "
            "VALUES (:event_id,:event_type,:occurred_at,:actor_user_id,CAST(:payload AS jsonb)) "
            "ON CONFLICT (event_id) DO NOTHING"
        ),
        values,
    )
    connection.execute(
        text(
            "INSERT INTO coeus_outbox"
            "(event_id,aggregate_id,aggregate_version,event_type,payload) "
            "VALUES (:event_id,:aggregate_id,:result_version,:event_type,CAST(:payload AS jsonb)) "
            "ON CONFLICT (aggregate_id,aggregate_version,event_type) DO NOTHING"
        ),
        values,
    )
