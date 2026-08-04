"""Immutable history, audit and outbox evidence for predecessor cancellation."""

import json
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.package_predecessor_cancellation import (
    CancelPredecessorCommand,
    DependantDispositionAction,
    cancellation_hash,
)
from coeus.persistence.package_predecessor_cancellation_sql import (
    AUDIT,
    COMMAND,
    HISTORY,
    OUTBOX,
)


def append_cancellation_history(
    connection: Connection,
    command: CancelPredecessorCommand,
    package_id: UUID,
    version: int,
    event: str,
    at: datetime,
) -> None:
    connection.execute(
        text(HISTORY),
        {
            "history_id": uuid5(
                NAMESPACE_URL, f"coeus:package-lifecycle:{command.command_id}:{package_id}"
            ),
            "package_id": package_id,
            "version": version,
            "actor_id": command.actor_user_id,
            "event": event,
            "evidence": json.dumps({"command_id": str(command.command_id)}),
            "at": at,
        },
    )


def append_cancellation_evidence(
    connection: Connection,
    command: CancelPredecessorCommand,
    version: int,
    counts: dict[DependantDispositionAction, int],
    at: datetime,
) -> None:
    payload = json.dumps(
        [
            {
                "package_id": str(item.dependant_package_id),
                "action": item.action.value,
                "replacement_package_id": (
                    str(item.replacement_package_id) if item.replacement_package_id else None
                ),
            }
            for item in command.request.dispositions
        ],
        sort_keys=True,
    )
    connection.execute(
        text(COMMAND),
        {
            "command_id": command.command_id,
            "actor_id": command.actor_user_id,
            "key": command.idempotency_key,
            "hash": cancellation_hash(command.actor_user_id, command.request),
            "package_id": command.request.package_id,
            "expected_version": command.request.expected_package_version,
            "result_version": version,
            "dispositions": payload,
            "at": at,
        },
    )
    event_id = uuid5(NAMESPACE_URL, f"coeus:predecessor-cancelled:{command.command_id}")
    evidence = json.dumps(
        {
            "package_id": str(command.request.package_id),
            "package_version": version,
            "disposition_counts": {key.value: value for key, value in counts.items()},
        },
        sort_keys=True,
    )
    values = {
        "event_id": event_id,
        "actor_id": command.actor_user_id,
        "at": at,
        "package_id": command.request.package_id,
        "version": version,
        "evidence": evidence,
    }
    connection.execute(text(AUDIT), values)
    connection.execute(text(OUTBOX), values)
