"""Saved board-view and package-template command writes."""

import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.domain.organisation import ManagementAction
from coeus.domain.team_task_board import TeamBoardQuery
from coeus.domain.workspace_productivity import (
    PackageTemplate,
    ProductivityCommand,
    SavedBoardView,
    WorkspaceRecordConflict,
    WorkspaceRecordDenied,
)
from coeus.persistence.team_task_board_authority import resolve_board_authority
from coeus.persistence.workspace_productivity_authority import require_action
from coeus.persistence.workspace_productivity_commands import integer_value, uuid_value
from coeus.persistence.workspace_productivity_execution import CommandRunner, require_command_grant
from coeus.persistence.workspace_productivity_records import (
    filters_json,
    parse_filters,
    template_row,
    view_row,
)
from coeus.persistence.workspace_productivity_result_codecs import (
    template_from_result,
    template_result,
    view_from_result,
    view_result,
)

_INSERT_VIEW = """
INSERT INTO workspace_saved_views(
  view_id,owner_user_id,unit_id,name,filters,version,created_at,updated_at
) VALUES (:id,:owner,:unit,:name,CAST(:filters AS jsonb),1,:now,:now)
"""
_UPDATE_VIEW = """
UPDATE workspace_saved_views SET unit_id=:unit,name=:name,
filters=CAST(:filters AS jsonb),version=version+1,updated_at=:now WHERE view_id=:id
"""
_INSERT_TEMPLATE = """
INSERT INTO team_work_templates(
  template_id,unit_id,owner_user_id,name,package_titles,estimated_minutes,
  priority,version,created_at,updated_at
) VALUES (:id,:unit,:owner,:name,CAST(:titles AS jsonb),:minutes,:priority,1,:now,:now)
"""
_UPDATE_TEMPLATE = """
UPDATE team_work_templates SET name=:name,package_titles=CAST(:titles AS jsonb),
estimated_minutes=:minutes,priority=:priority,version=version+1,updated_at=:now
WHERE template_id=:id
"""


class ViewTemplateWriter:
    def __init__(self, engine: Engine) -> None:
        self._view_runner = CommandRunner(engine)

    def save_view(self, command: ProductivityCommand) -> SavedBoardView:
        def apply(
            connection: Connection, now: datetime
        ) -> tuple[SavedBoardView, dict[str, object]]:
            payload = command.payload
            view_id = uuid_value(payload, "view_id")
            unit_id = uuid_value(payload, "unit_id")
            filters = parse_filters(payload.get("filters"))
            name = str(payload.get("name", ""))
            SavedBoardView(view_id, command.actor_user_id, unit_id, name, filters, 1, now)
            require_action(
                connection,
                command.actor_user_id,
                unit_id,
                ManagementAction.WORKSPACE_VIEW,
                now,
            )
            resolve_board_authority(
                connection,
                command.actor_user_id,
                unit_id,
                TeamBoardQuery(
                    scope=filters.scope,
                    include_completed=filters.include_completed,
                    columns=filters.columns,
                    unit_ids=filters.unit_ids,
                    priority=filters.priority,
                    due_from=filters.due_from,
                    due_to=filters.due_to,
                ),
                now,
            )
            existing = (
                connection.execute(
                    text("SELECT * FROM workspace_saved_views WHERE view_id=:id FOR UPDATE"),
                    {"id": view_id},
                )
                .mappings()
                .first()
            )
            expected = integer_value(payload, "expected_version")
            values = {
                "id": view_id,
                "owner": command.actor_user_id,
                "unit": unit_id,
                "name": name,
                "filters": filters_json(filters),
                "now": now,
            }
            if existing is None:
                if expected != 0:
                    raise WorkspaceRecordConflict("saved view version changed")
                connection.execute(text(_INSERT_VIEW), values)
            else:
                _require_owner_version(existing, command.actor_user_id, expected, "saved view")
                connection.execute(text(_UPDATE_VIEW), values)
            item = view_row(
                connection.execute(
                    text("SELECT * FROM workspace_saved_views WHERE view_id=:id"),
                    {"id": view_id},
                )
                .mappings()
                .one()
            )
            return item, view_result(item)

        return self._view_runner.run(command, view_from_result, apply)

    def delete_view(self, command: ProductivityCommand) -> bool:
        def apply(connection: Connection, now: datetime) -> tuple[bool, dict[str, object]]:
            view_id = uuid_value(command.payload, "view_id")
            row = (
                connection.execute(
                    text("SELECT * FROM workspace_saved_views WHERE view_id=:id FOR UPDATE"),
                    {"id": view_id},
                )
                .mappings()
                .first()
            )
            if row is None:
                raise WorkspaceRecordDenied
            _require_owner_version(
                row,
                command.actor_user_id,
                integer_value(command.payload, "expected_version"),
                "saved view",
            )
            require_action(
                connection,
                command.actor_user_id,
                UUID(str(row["unit_id"])),
                ManagementAction.WORKSPACE_VIEW,
                now,
            )
            connection.execute(
                text("DELETE FROM workspace_saved_views WHERE view_id=:id"), {"id": view_id}
            )
            result = {
                "deleted": True,
                "aggregate_id": str(view_id),
                "version": int(row["version"]) + 1,
            }
            return True, result

        return self._view_runner.run(command, lambda value: bool(value["deleted"]), apply)

    def save_template(self, command: ProductivityCommand) -> PackageTemplate:
        def apply(
            connection: Connection, now: datetime
        ) -> tuple[PackageTemplate, dict[str, object]]:
            payload = command.payload
            template_id = uuid_value(payload, "template_id")
            unit_id = uuid_value(payload, "unit_id")
            titles = payload.get("package_titles")
            if not isinstance(titles, list):
                raise ValueError("package titles are invalid")
            item = PackageTemplate(
                template_id,
                unit_id,
                command.actor_user_id,
                str(payload.get("name", "")),
                tuple(str(value) for value in titles),
                integer_value(payload, "estimated_minutes", optional=True),
                integer_value(payload, "priority", optional=True),
                1,
                now,
            )
            require_command_grant(connection, command, unit_id, now)
            existing = (
                connection.execute(
                    text("SELECT * FROM team_work_templates WHERE template_id=:id FOR UPDATE"),
                    {"id": template_id},
                )
                .mappings()
                .first()
            )
            expected = integer_value(payload, "expected_version")
            if existing is None and expected != 0:
                raise WorkspaceRecordConflict("template version changed")
            if existing is not None:
                _require_owner_version(existing, command.actor_user_id, expected, "template")
            values = _template_values(item, now)
            connection.execute(
                text(_INSERT_TEMPLATE if existing is None else _UPDATE_TEMPLATE), values
            )
            current = template_row(
                connection.execute(
                    text("SELECT * FROM team_work_templates WHERE template_id=:id"),
                    {"id": template_id},
                )
                .mappings()
                .one()
            )
            return current, template_result(current)

        return self._view_runner.run(command, template_from_result, apply)

    def delete_template(self, command: ProductivityCommand) -> bool:
        def apply(connection: Connection, now: datetime) -> tuple[bool, dict[str, object]]:
            template_id = uuid_value(command.payload, "template_id")
            row = (
                connection.execute(
                    text("SELECT * FROM team_work_templates WHERE template_id=:id FOR UPDATE"),
                    {"id": template_id},
                )
                .mappings()
                .first()
            )
            if row is None:
                raise WorkspaceRecordDenied
            _require_owner_version(
                row,
                command.actor_user_id,
                integer_value(command.payload, "expected_version"),
                "template",
            )
            require_command_grant(connection, command, UUID(str(row["unit_id"])), now)
            connection.execute(
                text("DELETE FROM team_work_templates WHERE template_id=:id"),
                {"id": template_id},
            )
            result = {
                "deleted": True,
                "aggregate_id": str(template_id),
                "version": int(row["version"]) + 1,
            }
            return True, result

        return self._view_runner.run(command, lambda value: bool(value["deleted"]), apply)


def _require_owner_version(row: RowMapping, actor: UUID, expected: int | None, label: str) -> None:
    if UUID(str(row["owner_user_id"])) != actor:
        raise WorkspaceRecordDenied
    if int(row["version"]) != expected:
        raise WorkspaceRecordConflict(f"{label} version changed")


def _template_values(item: PackageTemplate, now: datetime) -> dict[str, object]:
    return {
        "id": item.template_id,
        "unit": item.unit_id,
        "owner": item.owner_user_id,
        "name": item.name,
        "titles": json.dumps(item.package_titles),
        "minutes": item.estimated_minutes,
        "priority": item.priority,
        "now": now,
    }
