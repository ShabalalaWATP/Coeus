"""Row codecs and immutable evidence for workspace productivity."""

import json
from datetime import date, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.team_task_board import TeamBoardColumn, TeamBoardScope
from coeus.domain.workspace_productivity import (
    DeliveryMode,
    DeliveryPreferences,
    PackageTemplate,
    ProductivityCommand,
    SavedBoardFilters,
    SavedBoardView,
    WorkspaceStoreLink,
    WorkUpdate,
    WorkUpdateKind,
)


def filters_json(filters: SavedBoardFilters) -> str:
    return json.dumps(
        {
            "columns": [item.value for item in filters.columns],
            "due_from": filters.due_from.isoformat() if filters.due_from else None,
            "due_to": filters.due_to.isoformat() if filters.due_to else None,
            "include_completed": filters.include_completed,
            "priority": filters.priority,
            "scope": filters.scope.value,
            "unit_ids": [str(item) for item in filters.unit_ids],
        },
        sort_keys=True,
    )


def parse_filters(value: object) -> SavedBoardFilters:
    if not isinstance(value, dict):
        raise ValueError("saved board filters are malformed")
    return SavedBoardFilters(
        scope=TeamBoardScope(str(value.get("scope", "direct"))),
        include_completed=bool(value.get("include_completed", False)),
        columns=tuple(TeamBoardColumn(str(item)) for item in value.get("columns", [])),
        unit_ids=tuple(UUID(str(item)) for item in value.get("unit_ids", [])),
        priority=str(value["priority"]) if value.get("priority") is not None else None,
        due_from=date.fromisoformat(str(value["due_from"])) if value.get("due_from") else None,
        due_to=date.fromisoformat(str(value["due_to"])) if value.get("due_to") else None,
    )


def view_row(row: RowMapping) -> SavedBoardView:
    return SavedBoardView(
        UUID(str(row["view_id"])),
        UUID(str(row["owner_user_id"])),
        UUID(str(row["unit_id"])),
        str(row["name"]),
        parse_filters(dict(row["filters"])),
        int(row["version"]),
        row["updated_at"],
    )


def template_row(row: RowMapping) -> PackageTemplate:
    return PackageTemplate(
        UUID(str(row["template_id"])),
        UUID(str(row["unit_id"])),
        UUID(str(row["owner_user_id"])),
        str(row["name"]),
        tuple(str(item) for item in row["package_titles"]),
        int(row["estimated_minutes"]) if row["estimated_minutes"] is not None else None,
        int(row["priority"]) if row["priority"] is not None else None,
        int(row["version"]),
        row["updated_at"],
    )


def update_row(row: RowMapping) -> WorkUpdate:
    return WorkUpdate(
        UUID(str(row["update_id"])),
        UUID(str(row["recipient_user_id"])),
        str(row["event_key"]),
        WorkUpdateKind(str(row["kind"])),
        UUID(str(row["unit_id"])),
        str(row["object_type"]),
        UUID(str(row["object_id"])),
        row["occurred_at"],
        row["acknowledged_at"],
    )


def preference_row(row: RowMapping) -> DeliveryPreferences:
    return DeliveryPreferences(
        UUID(str(row["user_id"])),
        DeliveryMode(str(row["mode"])),
        bool(row["due_reminders"]),
        int(row["version"]),
    )


def store_link_row(row: RowMapping) -> WorkspaceStoreLink:
    return WorkspaceStoreLink(
        UUID(str(row["link_id"])),
        UUID(str(row["owner_user_id"])),
        UUID(str(row["unit_id"])),
        str(row["source_type"]),
        UUID(str(row["source_id"])),
        str(row["target_type"]),
        UUID(str(row["target_id"])),
        str(row["label"]),
        int(row["version"]),
        row["updated_at"],
    )


def append_evidence(
    connection: Connection,
    command: ProductivityCommand,
    aggregate_id: UUID,
    version: int,
    occurred_at: datetime,
) -> None:
    event_id = uuid5(NAMESPACE_URL, f"coeus:workspace:{command.command_id}")
    payload = json.dumps(
        {"aggregate_id": str(aggregate_id), "operation": command.operation, "version": version},
        sort_keys=True,
    )
    values = {
        "event_id": event_id,
        "event_type": f"workspace_{command.operation}",
        "occurred_at": occurred_at,
        "actor": command.actor_user_id,
        "aggregate": aggregate_id,
        "version": version,
        "payload": payload,
    }
    connection.execute(
        text(
            "INSERT INTO coeus_audit_events"
            "(event_id,event_type,occurred_at,actor_user_id,metadata) "
            "VALUES (:event_id,:event_type,:occurred_at,:actor,CAST(:payload AS jsonb))"
        ),
        values,
    )
    connection.execute(
        text(
            "INSERT INTO coeus_outbox(event_id,aggregate_id,aggregate_version,event_type,payload) "
            "VALUES (:event_id,:aggregate,:version,:event_type,CAST(:payload AS jsonb))"
        ),
        values,
    )
