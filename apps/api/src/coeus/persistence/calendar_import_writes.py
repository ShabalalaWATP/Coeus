"""Canonical and evidence writes for one legacy-calendar import."""

import json
from datetime import datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.calendar_import import (
    CalendarImportCommand,
    CalendarImportResult,
    LegacyCalendarCandidate,
)


def insert_imported_event(
    connection: Connection,
    candidate: LegacyCalendarCandidate,
    command: CalendarImportCommand,
    source_digest: str,
    occurred_at: datetime,
) -> None:
    values = _values(candidate, command, source_digest, occurred_at)
    connection.execute(text(_EVENT), values)
    connection.execute(text(_SCOPE), values)
    connection.execute(text(_HISTORY), values)
    connection.execute(text(_CALENDAR_COMMAND), values)
    connection.execute(text(_PROVENANCE), values)


def append_import_evidence(
    connection: Connection,
    command: CalendarImportCommand,
    result: CalendarImportResult,
    occurred_at: datetime,
) -> None:
    event_id = uuid5(NAMESPACE_URL, f"coeus:calendar-legacy-import:{command.command_id}")
    payload = json.dumps(
        {
            "command_id": str(command.command_id),
            "existing_count": result.existing_count,
            "imported_count": result.imported_count,
        },
        sort_keys=True,
    )
    values = {
        "event_id": event_id,
        "aggregate_id": command.command_id,
        "actor_id": command.actor_user_id,
        "occurred_at": occurred_at,
        "payload": payload,
    }
    connection.execute(text(_AUDIT), values)
    connection.execute(text(_OUTBOX), values)


def _values(
    candidate: LegacyCalendarCandidate,
    command: CalendarImportCommand,
    source_digest: str,
    occurred_at: datetime,
) -> dict[str, object]:
    snapshot = json.dumps(
        {
            "activity": candidate.activity.value,
            "all_day_end": candidate.all_day_end.isoformat(),
            "all_day_start": candidate.all_day_start.isoformat(),
            "availability": candidate.availability.value,
            "event_id": str(candidate.event_id),
            "owner_user_id": str(candidate.owner_user_id),
            "source": "legacy",
            "team_id": str(candidate.team_id),
            "version": 1,
        },
        sort_keys=True,
    )
    return {
        "entry_id": candidate.legacy_entry_id,
        "event_id": candidate.event_id,
        "scope_id": candidate.scope_id,
        "history_id": candidate.history_id,
        "calendar_command_id": candidate.calendar_command_id,
        "team_id": candidate.team_id,
        "owner_id": candidate.owner_user_id,
        "creator_id": candidate.creator_user_id,
        "start": candidate.all_day_start,
        "end": candidate.all_day_end,
        "activity": candidate.activity.value,
        "availability": candidate.availability.value,
        "note": candidate.note,
        "created_at": candidate.created_at,
        "occurred_at": occurred_at,
        "source_digest": source_digest,
        "import_command_id": command.command_id,
        "snapshot": snapshot,
        "reason_hash": sha256(b"legacy calendar import").hexdigest(),
        "request_hash": sha256(
            f"legacy-calendar-import-v1:{candidate.legacy_entry_id}".encode()
        ).hexdigest(),
        "calendar_idempotency": f"legacy-calendar-import-v1-{candidate.legacy_entry_id}",
    }


_EVENT = """
INSERT INTO calendar_events(event_id,owner_user_id,source,activity_category,
 starts_at,ends_at,all_day_start,all_day_end,time_zone,availability_effect,
 privacy_level,note,recurrence_rule,status,manager_scope_unit_id,created_by_user_id,
 created_at,updated_at,cancelled_at,version,provenance)
VALUES (:event_id,:owner_id,'legacy',:activity,NULL,NULL,:start,:end,'Europe/London',
 :availability,'team_summary',:note,NULL,'active',NULL,:creator_id,
 :created_at,:occurred_at,NULL,1,'legacy_import')
"""

_SCOPE = """
INSERT INTO calendar_event_scopes(scope_id,event_id,scope_type,subject_user_id,unit_id,created_at)
VALUES (:scope_id,:event_id,'team_participant',:owner_id,:team_id,:occurred_at)
"""

_HISTORY = """
INSERT INTO calendar_event_versions(history_id,event_id,event_version,snapshot,
 changed_by_user_id,changed_at,change_reason_hash)
VALUES (:history_id,:event_id,1,CAST(:snapshot AS jsonb),:creator_id,:occurred_at,:reason_hash)
"""

_CALENDAR_COMMAND = """
INSERT INTO calendar_event_commands(command_id,actor_user_id,idempotency_key,command_type,
 request_hash,event_id,result_version,created_at)
VALUES (:calendar_command_id,:creator_id,:calendar_idempotency,'create',:request_hash,
 :event_id,1,:occurred_at)
"""

_PROVENANCE = """
INSERT INTO calendar_legacy_import_records(legacy_entry_id,event_id,team_id,owner_user_id,
 creator_user_id,source_digest,command_id,imported_at)
VALUES (:entry_id,:event_id,:team_id,:owner_id,:creator_id,:source_digest,
 :import_command_id,:occurred_at)
"""

_AUDIT = """
INSERT INTO coeus_audit_events(event_id,event_type,occurred_at,actor_user_id,metadata)
VALUES (:event_id,'legacy_calendar_imported',:occurred_at,:actor_id,CAST(:payload AS jsonb))
"""

_OUTBOX = """
INSERT INTO coeus_outbox(event_id,aggregate_id,aggregate_version,event_type,payload)
VALUES (:event_id,:aggregate_id,1,'legacy_calendar_imported',CAST(:payload AS jsonb))
"""
