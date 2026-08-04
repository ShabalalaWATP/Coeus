"""Idempotent command support for workspace productivity writes."""

import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.workspace_productivity import ProductivityCommand, WorkspaceRecordConflict


def lock_command_key(connection: Connection, command: ProductivityCommand) -> None:
    connection.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:value,0))"),
        {"value": f"workspace:{command.actor_user_id}:{command.idempotency_key}"},
    ).scalar_one()


def replay_result(connection: Connection, command: ProductivityCommand) -> dict[str, object] | None:
    row = (
        connection.execute(
            text(
                "SELECT request_hash,operation,result FROM workspace_productivity_commands "
                "WHERE actor_user_id=:actor AND idempotency_key=:key"
            ),
            {"actor": command.actor_user_id, "key": command.idempotency_key},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    if row["request_hash"] != command.request_hash or row["operation"] != command.operation:
        raise WorkspaceRecordConflict("idempotency key was already used for another command")
    return dict(row["result"])


def record_command(
    connection: Connection,
    command: ProductivityCommand,
    result: dict[str, object],
    occurred_at: datetime,
) -> None:
    connection.execute(
        text(
            "INSERT INTO workspace_productivity_commands"
            "(command_id,actor_user_id,idempotency_key,request_hash,operation,result,occurred_at) "
            "VALUES (:command_id,:actor,:key,:hash,:operation,CAST(:result AS jsonb),:occurred_at)"
        ),
        {
            "command_id": command.command_id,
            "actor": command.actor_user_id,
            "key": command.idempotency_key,
            "hash": command.request_hash,
            "operation": command.operation,
            "result": json.dumps(result, default=str, sort_keys=True),
            "occurred_at": occurred_at,
        },
    )


def uuid_value(payload: dict[str, object], key: str) -> UUID:
    try:
        return UUID(str(payload[key]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{key} is invalid") from exc


def integer_value(payload: dict[str, object], key: str, *, optional: bool = False) -> int | None:
    value = payload.get(key)
    if value is None and optional:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{key} is invalid")
    if not isinstance(value, int | float | str):
        raise ValueError(f"{key} is invalid")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} is invalid") from exc
