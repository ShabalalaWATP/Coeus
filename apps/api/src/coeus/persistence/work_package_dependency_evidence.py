"""Immutable, bounded dependency command evidence."""

import json
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.work_package_dependencies import ChangeDependencyCommand


def append_dependency_evidence(
    connection: Connection,
    command: ChangeDependencyCommand,
    package_version: int,
    occurred_at: datetime,
) -> None:
    operation = command.request.operation.value
    event_type = f"work_package_dependency_{_past_tense(operation)}"
    event_id = uuid5(NAMESPACE_URL, f"coeus:{event_type}:{command.command_id}")
    payload = json.dumps(
        {
            "package_id": str(command.request.package_id),
            "predecessor_package_id": str(command.request.predecessor_package_id),
            "unit_id": str(command.request.unit_id),
            "version": package_version,
        },
        sort_keys=True,
    )
    values = {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": occurred_at,
        "actor_id": command.actor_user_id,
        "aggregate_id": command.request.package_id,
        "aggregate_version": package_version,
        "payload": payload,
    }
    connection.execute(
        text(
            "INSERT INTO coeus_audit_events"
            "(event_id,event_type,occurred_at,actor_user_id,metadata) "
            "VALUES (:event_id,:event_type,:occurred_at,:actor_id,CAST(:payload AS jsonb))"
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


def dependency_history_values(
    command: ChangeDependencyCommand,
    package_version: int,
    occurred_at: datetime,
) -> dict[str, object]:
    request = command.request
    return {
        "history_id": _history_id(request.package_id, package_version),
        "package_id": request.package_id,
        "version": package_version,
        "actor_id": command.actor_user_id,
        "event_type": f"dependency_{_past_tense(request.operation.value)}",
        "evidence": json.dumps(
            {
                "grant_id": str(request.authorising_grant_id),
                "grant_version": request.expected_grant_version,
                "ownership_version": request.expected_ownership_version,
                "predecessor_package_id": str(request.predecessor_package_id),
                "predecessor_package_version": request.expected_predecessor_version,
            },
            sort_keys=True,
        ),
        "at": occurred_at,
    }


def _history_id(package_id: UUID, version: int) -> UUID:
    return uuid5(NAMESPACE_URL, f"coeus:work-package-history:{package_id}:{version}")


def _past_tense(operation: str) -> str:
    return "removed" if operation == "remove" else "added"
