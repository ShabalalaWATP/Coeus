"""Actor-scoped command identity and replay for predecessor cancellation."""

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.package_predecessor_cancellation import (
    CancelPredecessorCommand,
    PredecessorCancellationConflict,
    PredecessorCancellationResult,
    cancellation_hash,
)
from coeus.persistence.package_predecessor_cancellation_sql import REPLAY


def lock_cancellation_identities(connection: Connection, command: CancelPredecessorCommand) -> None:
    for key in sorted(
        (
            f"predecessor-cancel:id:{command.command_id}",
            f"predecessor-cancel:key:{command.actor_user_id}:{command.idempotency_key}",
        )
    ):
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {"key": key}
        )


def replay_cancellation(
    connection: Connection, command: CancelPredecessorCommand
) -> PredecessorCancellationResult | None:
    rows = tuple(
        connection.execute(
            text(REPLAY),
            {
                "command_id": command.command_id,
                "actor_id": command.actor_user_id,
                "key": command.idempotency_key,
            },
        ).mappings()
    )
    if not rows:
        return None
    if len(rows) != 1 or rows[0]["request_hash"] != cancellation_hash(
        command.actor_user_id, command.request
    ):
        raise PredecessorCancellationConflict("predecessor cancellation identity was reused")
    dispositions = tuple(rows[0]["dispositions"])
    counts = {
        value: sum(item["action"] == value for item in dispositions)
        for value in ("cancel", "unlink", "replace")
    }
    return PredecessorCancellationResult(
        command.request.package_id,
        int(rows[0]["result_package_version"]),
        counts["cancel"],
        counts["unlink"],
        counts["replace"],
        True,
    )
