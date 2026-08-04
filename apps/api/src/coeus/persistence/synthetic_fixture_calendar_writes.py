"""Canonical calendar evidence writes for synthetic fixture scenarios."""

import json
from datetime import datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.synthetic_organisation_fixture import SyntheticFixtureUser
from coeus.persistence.synthetic_fixture_values import PROVENANCE, TIME_ZONE
from coeus.repositories.synthetic_calendar_manifest import SyntheticCalendarEventSpec
from coeus.repositories.synthetic_organisation_manifest import SyntheticUnitSpec


def insert_calendar_events(
    connection: Connection,
    specs: tuple[SyntheticCalendarEventSpec, ...],
    users: dict[str, SyntheticFixtureUser],
    units: dict[str, SyntheticUnitSpec],
    occurred_at: datetime,
) -> None:
    for spec in specs:
        owner = users[spec.owner_username.casefold()]
        creator = users[spec.created_by_username.casefold()]
        manager_scope = (
            units[spec.manager_scope_unit_key].unit_id if spec.manager_scope_unit_key else None
        )
        params = {
            "event_id": spec.event_id,
            "owner_id": owner.user_id,
            "source": spec.source.value,
            "activity": spec.activity.value,
            "starts_at": spec.starts_at,
            "ends_at": spec.ends_at,
            "all_day_start": spec.all_day_start,
            "all_day_end": spec.all_day_end,
            "time_zone": TIME_ZONE,
            "availability": spec.availability.value,
            "privacy": spec.privacy.value,
            "manager_scope": manager_scope,
            "creator_id": creator.user_id,
            "occurred_at": occurred_at,
            "provenance": PROVENANCE,
        }
        connection.execute(text(_INSERT_EVENT), params)
        _insert_scope(connection, spec, owner.user_id, "owner_global", None, occurred_at)
        if manager_scope is not None:
            _insert_scope(
                connection,
                spec,
                owner.user_id,
                "home_unit",
                manager_scope,
                occurred_at,
            )
        snapshot = json.dumps(
            {
                "event_id": str(spec.event_id),
                "owner_user_id": str(owner.user_id),
                "source": spec.source.value,
                "activity": spec.activity.value,
                "availability": spec.availability.value,
                "privacy": spec.privacy.value,
                "starts_at": spec.starts_at.isoformat() if spec.starts_at else None,
                "ends_at": spec.ends_at.isoformat() if spec.ends_at else None,
                "all_day_start": spec.all_day_start.isoformat() if spec.all_day_start else None,
                "all_day_end": spec.all_day_end.isoformat() if spec.all_day_end else None,
                "version": 1,
            },
            sort_keys=True,
        )
        connection.execute(
            text(_INSERT_HISTORY),
            {
                "history_id": spec.history_id,
                "event_id": spec.event_id,
                "snapshot": snapshot,
                "creator_id": creator.user_id,
                "occurred_at": occurred_at,
                "reason_hash": sha256(b"synthetic exercise calendar fixture").hexdigest(),
            },
        )
        connection.execute(
            text(_INSERT_COMMAND),
            {
                "command_id": spec.command_id,
                "creator_id": creator.user_id,
                "idempotency_key": f"synthetic-calendar-v2-{spec.key}",
                "request_hash": sha256(f"synthetic-calendar-v2:{spec.key}".encode()).hexdigest(),
                "event_id": spec.event_id,
                "occurred_at": occurred_at,
            },
        )


def _insert_scope(
    connection: Connection,
    spec: SyntheticCalendarEventSpec,
    owner_user_id: UUID,
    scope_type: str,
    unit_id: UUID | None,
    occurred_at: datetime,
) -> None:
    connection.execute(
        text(
            "INSERT INTO calendar_event_scopes"
            "(scope_id,event_id,scope_type,subject_user_id,unit_id,created_at) "
            "VALUES (:scope_id,:event_id,:scope_type,:owner_id,:unit_id,:occurred_at)"
        ),
        {
            "scope_id": spec.scope_id(scope_type),
            "event_id": spec.event_id,
            "scope_type": scope_type,
            "owner_id": owner_user_id,
            "unit_id": unit_id,
            "occurred_at": occurred_at,
        },
    )


_INSERT_EVENT = """
INSERT INTO calendar_events(event_id,owner_user_id,source,activity_category,
 starts_at,ends_at,all_day_start,all_day_end,time_zone,availability_effect,
 privacy_level,note,recurrence_rule,status,manager_scope_unit_id,created_by_user_id,
 created_at,updated_at,cancelled_at,version,provenance)
VALUES (:event_id,:owner_id,:source,:activity,:starts_at,:ends_at,:all_day_start,
 :all_day_end,:time_zone,:availability,:privacy,'',NULL,'active',:manager_scope,
 :creator_id,:occurred_at,:occurred_at,NULL,1,:provenance)
"""

_INSERT_HISTORY = """
INSERT INTO calendar_event_versions(history_id,event_id,event_version,snapshot,
 changed_by_user_id,changed_at,change_reason_hash)
VALUES (:history_id,:event_id,1,CAST(:snapshot AS jsonb),:creator_id,
 :occurred_at,:reason_hash)
"""

_INSERT_COMMAND = """
INSERT INTO calendar_event_commands(command_id,actor_user_id,idempotency_key,
 command_type,request_hash,event_id,result_version,created_at)
VALUES (:command_id,:creator_id,:idempotency_key,'create',:request_hash,
 :event_id,1,:occurred_at)
"""
