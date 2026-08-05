"""Privacy-safe work-update and delivery-preference writes."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from coeus.domain.organisation import ManagementAction
from coeus.domain.workspace_productivity import (
    DeliveryMode,
    DeliveryPreferences,
    ProductivityCommand,
    WorkspaceRecordConflict,
    WorkspaceRecordDenied,
    WorkUpdate,
    WorkUpdateKind,
)
from coeus.persistence.workspace_productivity_authority import (
    require_action,
    require_active_actor,
    require_update_object,
)
from coeus.persistence.workspace_productivity_commands import integer_value, uuid_value
from coeus.persistence.workspace_productivity_execution import CommandRunner, require_command_grant
from coeus.persistence.workspace_productivity_records import preference_row, update_row
from coeus.persistence.workspace_productivity_result_codecs import (
    update_from_result,
    update_result,
)

_INSERT_UPDATE = """
INSERT INTO workspace_work_updates(
  update_id,recipient_user_id,event_key,kind,unit_id,object_type,object_id,occurred_at
) VALUES (:id,:recipient,:event_key,:kind,:unit,:object_type,:object_id,:now)
ON CONFLICT(recipient_user_id,event_key) DO NOTHING
"""
_UPSERT_PREFERENCES = """
INSERT INTO workspace_delivery_preferences(user_id,mode,due_reminders,version,updated_at)
VALUES (:actor,:mode,:reminders,1,:now)
ON CONFLICT(user_id) DO UPDATE SET mode=:mode,due_reminders=:reminders,
version=workspace_delivery_preferences.version+1,updated_at=:now
"""


class UpdateWriter:
    def __init__(self, engine: Engine) -> None:
        self._update_runner = CommandRunner(engine)

    def deliver_update(self, command: ProductivityCommand) -> WorkUpdate:
        def apply(connection: Connection, now: datetime) -> tuple[WorkUpdate, dict[str, object]]:
            payload = command.payload
            update_id = uuid_value(payload, "update_id")
            recipient = uuid_value(payload, "recipient_user_id")
            unit_id = uuid_value(payload, "unit_id")
            object_id = uuid_value(payload, "object_id")
            require_command_grant(connection, command, unit_id, now)
            require_active_actor(connection, recipient, lock=True)
            require_action(connection, recipient, unit_id, ManagementAction.WORK_UPDATE_VIEW, now)
            object_type = str(payload.get("object_type", ""))
            require_update_object(connection, recipient, unit_id, object_type, object_id, now)
            event_key = str(payload.get("event_key", ""))
            if (
                not event_key
                or len(event_key) > 128
                or event_key != event_key.strip()
                or any(ord(character) < 32 for character in event_key)
            ):
                raise ValueError("event key is invalid")
            kind = WorkUpdateKind(str(payload.get("kind", "")))
            previous = (
                connection.execute(
                    text(
                        "SELECT * FROM workspace_work_updates "
                        "WHERE recipient_user_id=:recipient AND event_key=:event_key FOR UPDATE"
                    ),
                    {"recipient": recipient, "event_key": event_key},
                )
                .mappings()
                .first()
            )
            if previous is not None:
                existing = update_row(previous)
                if (
                    existing.kind is not kind
                    or existing.unit_id != unit_id
                    or existing.object_type != object_type
                    or existing.object_id != object_id
                ):
                    raise WorkspaceRecordConflict("work-update event key was reused")
                result = update_result(existing)
                result["mutated"] = False
                return existing, result
            connection.execute(
                text(_INSERT_UPDATE),
                {
                    "id": update_id,
                    "recipient": recipient,
                    "event_key": event_key,
                    "kind": kind.value,
                    "unit": unit_id,
                    "object_type": object_type,
                    "object_id": object_id,
                    "now": now,
                },
            )
            current = update_row(
                connection.execute(
                    text(
                        "SELECT * FROM workspace_work_updates "
                        "WHERE recipient_user_id=:recipient AND event_key=:event_key"
                    ),
                    {"recipient": recipient, "event_key": event_key},
                )
                .mappings()
                .one()
            )
            return current, update_result(current)

        return self._update_runner.run(command, update_from_result, apply)

    def acknowledge_update(self, command: ProductivityCommand) -> WorkUpdate:
        def apply(connection: Connection, now: datetime) -> tuple[WorkUpdate, dict[str, object]]:
            update_id = uuid_value(command.payload, "update_id")
            row = (
                connection.execute(
                    text("SELECT * FROM workspace_work_updates WHERE update_id=:id FOR UPDATE"),
                    {"id": update_id},
                )
                .mappings()
                .first()
            )
            if row is None or UUID(str(row["recipient_user_id"])) != command.actor_user_id:
                raise WorkspaceRecordDenied
            item = update_row(row)
            require_action(
                connection,
                command.actor_user_id,
                item.unit_id,
                ManagementAction.WORK_UPDATE_VIEW,
                now,
            )
            require_update_object(
                connection,
                command.actor_user_id,
                item.unit_id,
                item.object_type,
                item.object_id,
                now,
            )
            connection.execute(
                text(
                    "UPDATE workspace_work_updates SET "
                    "acknowledged_at=COALESCE(acknowledged_at,:now) WHERE update_id=:id"
                ),
                {"id": update_id, "now": now},
            )
            current = update_row(
                connection.execute(
                    text("SELECT * FROM workspace_work_updates WHERE update_id=:id"),
                    {"id": update_id},
                )
                .mappings()
                .one()
            )
            return current, update_result(current)

        return self._update_runner.run(command, update_from_result, apply)

    def save_preferences(self, command: ProductivityCommand) -> DeliveryPreferences:
        def apply(
            connection: Connection, now: datetime
        ) -> tuple[DeliveryPreferences, dict[str, object]]:
            mode = DeliveryMode(str(command.payload.get("mode", "")))
            reminders = command.payload.get("due_reminders")
            if not isinstance(reminders, bool):
                raise ValueError("due reminders setting is invalid")
            row = (
                connection.execute(
                    text(
                        "SELECT * FROM workspace_delivery_preferences "
                        "WHERE user_id=:actor FOR UPDATE"
                    ),
                    {"actor": command.actor_user_id},
                )
                .mappings()
                .first()
            )
            current_version = int(str(row["version"])) if row else 0
            if integer_value(command.payload, "expected_version") != current_version:
                raise WorkspaceRecordConflict("delivery preferences version changed")
            connection.execute(
                text(_UPSERT_PREFERENCES),
                {
                    "actor": command.actor_user_id,
                    "mode": mode.value,
                    "reminders": reminders,
                    "now": now,
                },
            )
            item = preference_row(
                connection.execute(
                    text("SELECT * FROM workspace_delivery_preferences WHERE user_id=:actor"),
                    {"actor": command.actor_user_id},
                )
                .mappings()
                .one()
            )
            result = {
                "aggregate_id": str(item.user_id),
                "due_reminders": item.due_reminders,
                "mode": item.mode.value,
                "version": item.version,
            }
            return item, result

        return self._update_runner.run(command, _preferences_from_result, apply)


def _preferences_from_result(value: dict[str, object]) -> DeliveryPreferences:
    return DeliveryPreferences(
        UUID(str(value["aggregate_id"])),
        DeliveryMode(str(value["mode"])),
        bool(value["due_reminders"]),
        int(str(value["version"])),
    )
