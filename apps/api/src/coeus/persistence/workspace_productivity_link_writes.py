"""Non-authoritative Store link command writes."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from coeus.domain.workspace_productivity import (
    ProductivityCommand,
    WorkspaceRecordConflict,
    WorkspaceRecordDenied,
    WorkspaceStoreLink,
)
from coeus.persistence.workspace_productivity_authority import require_link_source
from coeus.persistence.workspace_productivity_commands import integer_value, uuid_value
from coeus.persistence.workspace_productivity_execution import CommandRunner
from coeus.persistence.workspace_productivity_records import store_link_row


class StoreLinkWriter:
    def __init__(self, engine: Engine) -> None:
        self._link_runner = CommandRunner(engine)

    def save_store_link(self, command: ProductivityCommand) -> WorkspaceStoreLink:
        def apply(
            connection: Connection, now: datetime
        ) -> tuple[WorkspaceStoreLink, dict[str, object]]:
            payload = command.payload
            link_id = uuid_value(payload, "link_id")
            unit_id = uuid_value(payload, "unit_id")
            source_type = str(payload.get("source_type", ""))
            source_id = uuid_value(payload, "source_id")
            target_type = str(payload.get("target_type", ""))
            target_id = uuid_value(payload, "target_id")
            label = str(payload.get("label", ""))
            expected = integer_value(payload, "expected_version")
            candidate = WorkspaceStoreLink(
                link_id,
                command.actor_user_id,
                unit_id,
                source_type,
                source_id,
                target_type,
                target_id,
                label,
                1,
                now,
            )
            require_link_source(
                connection, command.actor_user_id, unit_id, source_type, source_id, now
            )
            existing = (
                connection.execute(
                    text("SELECT * FROM workspace_store_links WHERE link_id=:id FOR UPDATE"),
                    {"id": link_id},
                )
                .mappings()
                .first()
            )
            if existing is None:
                if expected != 0:
                    raise WorkspaceRecordConflict("Store link version changed")
                connection.execute(text(_INSERT), _values(candidate, now))
            else:
                if UUID(str(existing["owner_user_id"])) != command.actor_user_id:
                    raise WorkspaceRecordDenied
                if int(existing["version"]) != expected:
                    raise WorkspaceRecordConflict("Store link version changed")
                connection.execute(text(_UPDATE), _values(candidate, now))
            current = store_link_row(
                connection.execute(
                    text("SELECT * FROM workspace_store_links WHERE link_id=:id"),
                    {"id": link_id},
                )
                .mappings()
                .one()
            )
            return current, _result(current)

        return self._link_runner.run(command, _decode, apply)

    def delete_store_link(self, command: ProductivityCommand) -> bool:
        def apply(connection: Connection, now: datetime) -> tuple[bool, dict[str, object]]:
            link_id = uuid_value(command.payload, "link_id")
            row = (
                connection.execute(
                    text("SELECT * FROM workspace_store_links WHERE link_id=:id FOR UPDATE"),
                    {"id": link_id},
                )
                .mappings()
                .first()
            )
            if row is None or UUID(str(row["owner_user_id"])) != command.actor_user_id:
                raise WorkspaceRecordDenied
            if int(row["version"]) != integer_value(command.payload, "expected_version"):
                raise WorkspaceRecordConflict("Store link version changed")
            require_link_source(
                connection,
                command.actor_user_id,
                UUID(str(row["unit_id"])),
                str(row["source_type"]),
                UUID(str(row["source_id"])),
                now,
            )
            connection.execute(
                text("DELETE FROM workspace_store_links WHERE link_id=:id"), {"id": link_id}
            )
            result = {
                "deleted": True,
                "aggregate_id": str(link_id),
                "version": int(row["version"]) + 1,
            }
            return True, result

        return self._link_runner.run(command, lambda value: bool(value["deleted"]), apply)


_INSERT = """
INSERT INTO workspace_store_links(
 link_id,owner_user_id,unit_id,source_type,source_id,target_type,target_id,label,
 version,created_at,updated_at
) VALUES (:id,:owner,:unit,:source_type,:source_id,:target_type,:target_id,:label,1,:now,:now)
"""
_UPDATE = """
UPDATE workspace_store_links SET unit_id=:unit,source_type=:source_type,source_id=:source_id,
target_type=:target_type,target_id=:target_id,label=:label,version=version+1,updated_at=:now
WHERE link_id=:id
"""


def _values(item: WorkspaceStoreLink, now: datetime) -> dict[str, object]:
    return {
        "id": item.link_id,
        "owner": item.owner_user_id,
        "unit": item.unit_id,
        "source_type": item.source_type,
        "source_id": item.source_id,
        "target_type": item.target_type,
        "target_id": item.target_id,
        "label": item.label,
        "now": now,
    }


def _result(item: WorkspaceStoreLink) -> dict[str, object]:
    return {
        "aggregate_id": str(item.link_id),
        "version": item.version,
        "owner": str(item.owner_user_id),
        "unit": str(item.unit_id),
        "source_type": item.source_type,
        "source_id": str(item.source_id),
        "target_type": item.target_type,
        "target_id": str(item.target_id),
        "label": item.label,
        "updated_at": item.updated_at.isoformat(),
    }


def _decode(value: dict[str, object]) -> WorkspaceStoreLink:
    return WorkspaceStoreLink(
        UUID(str(value["aggregate_id"])),
        UUID(str(value["owner"])),
        UUID(str(value["unit"])),
        str(value["source_type"]),
        UUID(str(value["source_id"])),
        str(value["target_type"]),
        UUID(str(value["target_id"])),
        str(value["label"]),
        int(str(value["version"])),
        datetime.fromisoformat(str(value["updated_at"])),
    )
