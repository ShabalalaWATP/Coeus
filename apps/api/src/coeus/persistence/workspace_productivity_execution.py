"""Shared serialisable command execution for workspace productivity."""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from sqlalchemy.engine import Connection, Engine

from coeus.domain.organisation import ManagementAction
from coeus.domain.workspace_productivity import ProductivityCommand
from coeus.persistence.organisation_authority_validation import transaction_time
from coeus.persistence.workspace_productivity_authority import require_action, require_active_actor
from coeus.persistence.workspace_productivity_commands import (
    integer_value,
    lock_command_key,
    record_command,
    replay_result,
    uuid_value,
)
from coeus.persistence.workspace_productivity_records import append_evidence


class CommandRunner:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def run[T](
        self,
        command: ProductivityCommand,
        decode: Callable[[dict[str, object]], T],
        apply: Callable[[Connection, datetime], tuple[T, dict[str, object]]],
    ) -> T:
        with (
            self._engine.connect().execution_options(isolation_level="SERIALIZABLE") as connection,
            connection.begin(),
        ):
            require_active_actor(connection, command.actor_user_id, lock=True)
            lock_command_key(connection, command)
            replay = replay_result(connection, command)
            if replay is not None:
                return decode(replay)
            now = transaction_time(connection)
            item, result = apply(connection, now)
            record_command(connection, command, result, now)
            if result.get("mutated", True):
                append_evidence(
                    connection,
                    command,
                    UUID(str(result["aggregate_id"])),
                    int(str(result["version"])),
                    now,
                )
            return item


def require_command_grant(
    connection: Connection,
    command: ProductivityCommand,
    unit_id: UUID,
    now: datetime,
) -> None:
    require_action(
        connection,
        command.actor_user_id,
        unit_id,
        ManagementAction.WORKSPACE_CONFIGURE,
        now,
        grant_id=uuid_value(command.payload, "authorising_grant_id"),
        expected_version=integer_value(command.payload, "expected_grant_version"),
    )
