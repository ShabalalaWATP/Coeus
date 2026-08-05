"""Privacy-bounded immutable evidence for package planning."""

import json
from datetime import datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.work_package_planning import PlanWorkPackageCommand


def append_planning_evidence(
    connection: Connection,
    command: PlanWorkPackageCommand,
    package_version: int,
    occurred_at: datetime,
) -> None:
    event_type = "work_package_planned_and_reserved"
    event_id = uuid5(NAMESPACE_URL, f"coeus:{event_type}:{command.command_id}")
    payload = json.dumps(
        {
            "package_id": str(command.request.package_id),
            "reservation_id": str(command.request.reservation_id),
            "unit_id": str(command.request.unit_id),
            "version": package_version,
            "reason_hash": sha256(
                command.request.priority_override_reason.strip().encode()
            ).hexdigest(),
        },
        sort_keys=True,
    )
    values = {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": occurred_at,
        "actor_user_id": command.actor_user_id,
        "aggregate_id": command.request.package_id,
        "aggregate_version": package_version,
        "payload": payload,
    }
    connection.execute(
        text(
            "INSERT INTO coeus_audit_events"
            "(event_id,event_type,occurred_at,actor_user_id,metadata) "
            "VALUES (:event_id,:event_type,:occurred_at,:actor_user_id,CAST(:payload AS jsonb))"
        ),
        values,
    )
    connection.execute(
        text(
            "INSERT INTO coeus_outbox"
            "(event_id,aggregate_id,aggregate_version,event_type,payload) "
            "VALUES (:event_id,:aggregate_id,:aggregate_version,:event_type,"
            "CAST(:payload AS jsonb))"
        ),
        values,
    )


def planning_history_values(
    command: PlanWorkPackageCommand,
    package_version: int,
    occurred_at: datetime,
) -> dict[str, object]:
    evidence = json.dumps(
        {
            "due_at": command.request.due_at.isoformat(),
            "estimated_minutes": command.request.estimated_minutes,
            "priority": command.request.priority,
            "remaining_minutes": command.request.remaining_minutes,
            "reservation_id": str(command.request.reservation_id),
            "reserved_minutes": command.request.reserved_minutes,
        },
        sort_keys=True,
    )
    return {
        "history_id": _history_id(command.request.package_id, package_version),
        "package_id": command.request.package_id,
        "version": package_version,
        "actor_user_id": command.actor_user_id,
        "evidence": evidence,
        "occurred_at": occurred_at,
    }


def _history_id(package_id: UUID, version: int) -> UUID:
    return uuid5(NAMESPACE_URL, f"coeus:work-package-history:{package_id}:{version}")
