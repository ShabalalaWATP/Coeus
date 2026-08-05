"""Serialisable PostgreSQL organisation membership command store."""

import json
from datetime import datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_membership import (
    MembershipCommandConflict,
    MembershipIdempotencyConflict,
    MembershipMutationCommand,
    MembershipMutationRequest,
    MembershipMutationResult,
    MembershipMutationSnapshot,
    MembershipOperation,
    membership_hash,
)
from coeus.persistence import organisation_membership_sql as sql
from coeus.persistence.organisation_authority_validation import (
    lock_lineages,
    transaction_time,
    validate_lineage,
)
from coeus.persistence.organisation_membership_evidence import append_membership_evidence
from coeus.persistence.serializable_retry import retry_serializable_once


class PostgresOrganisationMembershipStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def inspect(self, request: MembershipMutationRequest) -> MembershipMutationSnapshot:
        with self._engine.begin() as connection:
            return _snapshot(connection, request)

    def replay(self, command: MembershipMutationCommand) -> MembershipMutationResult | None:
        with self._engine.begin() as connection:
            return _replay(_load_command(connection, command), command)

    def apply(self, command: MembershipMutationCommand) -> MembershipMutationResult:
        return retry_serializable_once(lambda: self._apply_once(command))

    def _apply_once(self, command: MembershipMutationCommand) -> MembershipMutationResult:
        with self._engine.begin() as connection:
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
            _locks(connection, command)
            replay = _replay(_load_command(connection, command), command)
            if replay is not None:
                return replay
            occurred_at = transaction_time(connection)
            request = command.request
            _validate_authority(connection, command, occurred_at)
            snapshot = _snapshot(connection, request)
            if membership_hash(request, command.actor_user_id, snapshot) != command.preview_hash:
                raise MembershipCommandConflict("the membership preview is stale")
            result = _mutate(connection, command, occurred_at)
            _write_command(connection, command, result, occurred_at)
            append_membership_evidence(connection, command, result, occurred_at)
            return result


def _locks(connection: Connection, command: MembershipMutationCommand) -> None:
    request = command.request
    values = (
        f"grant:{request.authorising_grant_id}",
        f"idempotency:{command.idempotency_key}",
        f"membership:{request.membership_id}",
        f"user-membership:{request.user_id}",
    )
    for value in sorted(values):
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:value, 0))"), {"value": value}
        )
    connection.execute(text(sql.LOCK_MEMBERSHIPS), vars(request)).all()


def _load_command(
    connection: Connection, command: MembershipMutationCommand
) -> tuple[RowMapping, ...]:
    return tuple(
        connection.execute(
            text(sql.LOAD_COMMAND),
            {"command_id": command.command_id, "idempotency_key": command.idempotency_key},
        ).mappings()
    )


def _replay(
    rows: tuple[RowMapping, ...], command: MembershipMutationCommand
) -> MembershipMutationResult | None:
    if not rows:
        return None
    if len(rows) != 1:
        raise MembershipIdempotencyConflict(
            "command and idempotency key identify different membership operations"
        )
    row = rows[0]
    request = command.request
    matches = (
        UUID(str(row["command_id"])) == command.command_id
        and str(row["idempotency_key"]) == command.idempotency_key
        and str(row["request_hash"]) == command.preview_hash
        and UUID(str(row["actor_user_id"])) == command.actor_user_id
        and UUID(str(row["membership_id"])) == request.membership_id
        and UUID(str(row["user_id"])) == request.user_id
        and UUID(str(row["unit_id"])) == request.unit_id
        and UUID(str(row["authorising_grant_id"])) == request.authorising_grant_id
        and str(row["operation"]) == request.operation.value
        and int(str(row["expected_version"])) == request.expected_version
        and str(row["role"]) == request.role.value
        and bool(row["assignment_eligible"]) == request.assignment_eligible
        and row["valid_from"] == request.valid_from
        and row["valid_until"] == request.valid_until
        and str(row["reason_hash"]) == sha256(request.reason.encode()).hexdigest()
    )
    if not matches:
        raise MembershipIdempotencyConflict(
            "command or idempotency key is already used by another membership operation"
        )
    return MembershipMutationResult(request.membership_id, int(str(row["result_version"])), True)


def _validate_authority(
    connection: Connection, command: MembershipMutationCommand, occurred_at: datetime
) -> None:
    request = command.request
    unit = (
        connection.execute(
            text("SELECT is_active FROM organisation_units WHERE unit_id=:unit_id FOR UPDATE"),
            vars(request),
        )
        .mappings()
        .first()
    )
    if unit is None or not bool(unit["is_active"]):
        raise MembershipCommandConflict("the organisation unit is not active")
    if (
        request.operation is MembershipOperation.END
        and request.valid_until is not None
        and request.valid_until > occurred_at
    ):
        raise MembershipCommandConflict("future membership endings require a transfer command")
    lock_lineages(connection, (request.authorising_grant_id,))
    validate_lineage(
        connection,
        request.authorising_grant_id,
        command.actor_user_id,
        request.unit_id,
        ManagementAction.ROSTER_MANAGE,
        occurred_at,
    )


def _snapshot(
    connection: Connection, request: MembershipMutationRequest
) -> MembershipMutationSnapshot:
    row = connection.execute(text(sql.INSPECT), vars(request)).mappings().first()
    if row is None:
        raise MembershipCommandConflict("the organisation unit is unavailable")
    digest = sha256(
        json.dumps(
            {
                "membership_id": str(request.membership_id),
                "user_id": str(request.user_id),
                "state": str(row["state_value"]),
                "active_task_legs": int(str(row["active_task_legs"])),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return MembershipMutationSnapshot(
        int(str(row["unit_version"])),
        int(str(row["membership_version"])),
        int(str(row["active_task_legs"])),
        digest,
    )


def _mutate(
    connection: Connection, command: MembershipMutationCommand, occurred_at: datetime
) -> MembershipMutationResult:
    request = command.request
    params = {
        **vars(request),
        "operation": request.operation.value,
        "role": request.role.value,
        "actor_user_id": command.actor_user_id,
        "occurred_at": occurred_at,
    }
    if request.operation is MembershipOperation.CREATE:
        if connection.execute(text(sql.OVERLAP), params).first() is not None:
            raise MembershipCommandConflict("the user already has an overlapping membership")
        statement = sql.INSERT_MEMBERSHIP
    elif request.operation is MembershipOperation.UPDATE:
        statement = sql.UPDATE_MEMBERSHIP
    else:
        statement = sql.END_MEMBERSHIP
    version = connection.execute(text(statement), params).scalar_one_or_none()
    if version is None:
        raise MembershipCommandConflict("the membership identity or version is stale")
    return MembershipMutationResult(request.membership_id, int(version))


def _write_command(
    connection: Connection,
    command: MembershipMutationCommand,
    result: MembershipMutationResult,
    occurred_at: datetime,
) -> None:
    request = command.request
    values = {
        **vars(request),
        "operation": request.operation.value,
        "role": request.role.value,
        "command_id": command.command_id,
        "idempotency_key": command.idempotency_key,
        "actor_user_id": command.actor_user_id,
        "request_hash": command.preview_hash,
        "reason_hash": sha256(request.reason.encode()).hexdigest(),
        "result_version": result.version,
        "occurred_at": occurred_at,
    }
    connection.execute(text(sql.INSERT_COMMAND), values).one()
