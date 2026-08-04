"""Serializable PostgreSQL adapter for explicit legacy-calendar imports."""

from datetime import datetime
from hashlib import sha256

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.application.ports.calendar_import import CalendarImportStore
from coeus.domain.calendar_import import (
    CalendarImportCommand,
    CalendarImportConflict,
    CalendarImportInspection,
    CalendarImportResult,
    LegacyCalendarCandidate,
    calendar_import_preview_hash,
)
from coeus.persistence.calendar_import_inspection import inspect_calendar_import
from coeus.persistence.calendar_import_writes import (
    append_import_evidence,
    insert_imported_event,
)


class PostgresCalendarImportStore(CalendarImportStore):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def inspect(self, candidates: tuple[LegacyCalendarCandidate, ...]) -> CalendarImportInspection:
        with (
            self._engine.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as connection,
            connection.begin(),
        ):
            return inspect_calendar_import(connection, candidates)

    def replay(self, command: CalendarImportCommand) -> CalendarImportResult | None:
        with self._engine.connect() as connection:
            return _replay(connection, command)

    def apply(
        self,
        command: CalendarImportCommand,
        source_digest: str,
        candidates: tuple[LegacyCalendarCandidate, ...],
    ) -> CalendarImportResult:
        with (
            self._engine.connect().execution_options(isolation_level="SERIALIZABLE") as connection,
            connection.begin(),
        ):
            replay = _replay(connection, command)
            if replay is not None:
                return replay
            inspection = inspect_calendar_import(connection, candidates)
            expected = calendar_import_preview_hash(
                command.actor_user_id, source_digest, inspection.state_digest
            )
            if expected != command.preview_hash:
                raise CalendarImportConflict("the legacy calendar import preview is stale")
            if inspection.findings:
                raise CalendarImportConflict("the legacy calendar contains blocking findings")
            occurred_at = connection.execute(text("SELECT transaction_timestamp()")).scalar_one()
            if not isinstance(occurred_at, datetime):
                raise RuntimeError("calendar import transaction time is unavailable")
            result = CalendarImportResult(
                command.command_id,
                len(inspection.importable),
                inspection.existing_count,
                False,
            )
            connection.execute(
                text(_INSERT_COMMAND),
                {
                    "command_id": command.command_id,
                    "actor_id": command.actor_user_id,
                    "idempotency_key": command.idempotency_key,
                    "request_hash": _request_hash(command),
                    "preview_hash": command.preview_hash,
                    "source_digest": source_digest,
                    "imported_count": result.imported_count,
                    "existing_count": result.existing_count,
                    "occurred_at": occurred_at,
                },
            )
            for candidate in inspection.importable:
                insert_imported_event(connection, candidate, command, source_digest, occurred_at)
            append_import_evidence(connection, command, result, occurred_at)
            return result


def _replay(connection: Connection, command: CalendarImportCommand) -> CalendarImportResult | None:
    rows = tuple(
        connection.execute(
            text(_LOAD_COMMAND),
            {
                "command_id": command.command_id,
                "actor_id": command.actor_user_id,
                "idempotency_key": command.idempotency_key,
            },
        ).mappings()
    )
    if not rows:
        return None
    if len(rows) != 1 or not _same_command(rows[0], command):
        raise CalendarImportConflict("calendar import command identity is already in use")
    row = rows[0]
    return CalendarImportResult(
        row["command_id"],
        int(row["imported_count"]),
        int(row["existing_count"]),
        True,
    )


def _same_command(row: RowMapping, command: CalendarImportCommand) -> bool:
    return (
        str(row["actor_user_id"]) == str(command.actor_user_id)
        and row["idempotency_key"] == command.idempotency_key
        and row["request_hash"] == _request_hash(command)
        and row["preview_hash"] == command.preview_hash
    )


def _request_hash(command: CalendarImportCommand) -> str:
    value = (
        f"calendar-import-command-v1:{command.actor_user_id}:"
        f"{command.idempotency_key}:{command.preview_hash}"
    )
    return sha256(value.encode()).hexdigest()


_LOAD_COMMAND = """
SELECT command_id,actor_user_id,idempotency_key,request_hash,preview_hash,
       imported_count,existing_count
FROM calendar_import_commands
WHERE command_id=:command_id
   OR (actor_user_id=:actor_id AND idempotency_key=:idempotency_key)
ORDER BY command_id
"""

_INSERT_COMMAND = """
INSERT INTO calendar_import_commands(command_id,actor_user_id,idempotency_key,request_hash,
 preview_hash,source_digest,imported_count,existing_count,occurred_at)
VALUES (:command_id,:actor_id,:idempotency_key,:request_hash,:preview_hash,:source_digest,
 :imported_count,:existing_count,:occurred_at)
"""
