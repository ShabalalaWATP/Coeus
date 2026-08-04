"""Transactional PostgreSQL create/edit organisation unit commands."""

import json
from datetime import datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_lifecycle import (
    OrganisationMutationCommand,
    OrganisationMutationConflict,
    OrganisationMutationIdempotencyConflict,
    OrganisationMutationOperation,
    OrganisationMutationResult,
    mutation_hash,
)
from coeus.persistence import organisation_lifecycle_sql as sql
from coeus.persistence.organisation_authority_validation import (
    lock_lineages,
    transaction_time,
    validate_lineage,
)
from coeus.persistence.serializable_retry import retry_serializable_once


class PostgresOrganisationMutationStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def replay(self, command: OrganisationMutationCommand) -> OrganisationMutationResult | None:
        with self._engine.begin() as connection:
            return _replay(_load_command(connection, command), command)

    def apply(self, command: OrganisationMutationCommand) -> OrganisationMutationResult:
        return retry_serializable_once(lambda: self._apply_once(command))

    def _apply_once(self, command: OrganisationMutationCommand) -> OrganisationMutationResult:
        with self._engine.begin() as connection:
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
            _command_locks(connection, command)
            replay = _replay(_load_command(connection, command), command)
            if replay is not None:
                return replay
            occurred_at = transaction_time(connection)
            if command.request.operation is OrganisationMutationOperation.CREATE:
                result = _create_unit(connection, command, occurred_at)
            else:
                result = _edit_unit(connection, command, occurred_at)
            _write_command(connection, command, result, occurred_at)
            _advance_epoch(connection, command, occurred_at)
            _append_evidence(connection, command, result, occurred_at)
            return result


def _command_locks(connection: Connection, command: OrganisationMutationCommand) -> None:
    request = command.request
    values = {
        f"idempotency:{command.idempotency_key}",
        f"grant:{request.authorising_grant_id}",
        f"unit:{request.unit_id}",
    }
    if request.parent_unit_id is not None:
        values.add(f"unit:{request.parent_unit_id}")
    for value in sorted(values):
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:value, 0))"), {"value": value}
        )


def _load_command(
    connection: Connection, command: OrganisationMutationCommand
) -> tuple[RowMapping, ...]:
    return tuple(
        connection.execute(
            text(sql.LOAD_COMMAND),
            {"command_id": command.command_id, "idempotency_key": command.idempotency_key},
        ).mappings()
    )


def _replay(
    rows: tuple[RowMapping, ...], command: OrganisationMutationCommand
) -> OrganisationMutationResult | None:
    if not rows:
        return None
    if len(rows) != 1:
        raise OrganisationMutationIdempotencyConflict(
            "command and idempotency key identify different mutations"
        )
    row = rows[0]
    request = command.request
    matches = (
        UUID(str(row["command_id"])) == command.command_id
        and str(row["idempotency_key"]) == command.idempotency_key
        and str(row["request_hash"]) == command.preview_hash
        and str(row["operation"]) == request.operation.value
        and UUID(str(row["actor_user_id"])) == command.actor_user_id
        and UUID(str(row["unit_id"])) == request.unit_id
    )
    if not matches:
        raise OrganisationMutationIdempotencyConflict(
            "command or idempotency key is already used by another mutation"
        )
    return OrganisationMutationResult(
        request.unit_id,
        int(str(row["result_version"])),
        _uuid(row["topology_revision_id"]),
        True,
    )


def _create_unit(
    connection: Connection, command: OrganisationMutationCommand, occurred_at: datetime
) -> OrganisationMutationResult:
    request = command.request
    parent_id = request.parent_unit_id
    assert parent_id is not None
    parent = _locked_unit(connection, parent_id)
    if parent is None or not bool(parent["is_active"]):
        raise OrganisationMutationConflict("the parent unit is not active")
    if int(str(parent["version"])) != request.expected_version:
        raise OrganisationMutationConflict("the parent unit version is stale")
    if _locked_unit(connection, request.unit_id) is not None:
        raise OrganisationMutationConflict("the new unit identity is already in use")
    _require_grant(
        connection, command, parent_id, ManagementAction.ORGANISATION_CREATE, occurred_at
    )
    depth = connection.execute(
        text(
            "SELECT COALESCE(max(depth),0) FROM organisation_unit_closure "
            "WHERE descendant_unit_id=:parent_id"
        ),
        {"parent_id": parent_id},
    ).scalar_one()
    if int(depth) >= 12:
        raise OrganisationMutationConflict("the organisation depth limit would be exceeded")
    params = _request_params(command, occurred_at)
    connection.execute(text(sql.INSERT_UNIT), params).one()
    connection.execute(text(sql.INSERT_CLOSURE), params)
    revision_id = uuid5(NAMESPACE_URL, f"coeus:organisation:revision:{command.command_id}")
    params["revision_id"] = revision_id
    connection.execute(text(sql.INSERT_REVISION), params).one()
    return OrganisationMutationResult(request.unit_id, 1, revision_id)


def _edit_unit(
    connection: Connection, command: OrganisationMutationCommand, occurred_at: datetime
) -> OrganisationMutationResult:
    request = command.request
    unit = _locked_unit(connection, request.unit_id)
    if unit is None or not bool(unit["is_active"]):
        raise OrganisationMutationConflict("the organisation unit is not active")
    if int(str(unit["version"])) != request.expected_version:
        raise OrganisationMutationConflict("the organisation unit version is stale")
    if str(unit["category"]) != request.category.value:
        raise OrganisationMutationConflict("unit category requires a restructure command")
    _require_grant(
        connection, command, request.unit_id, ManagementAction.ORGANISATION_EDIT, occurred_at
    )
    material = ("name", "short_name", "time_zone", "description")
    if all(str(unit[field]) == str(getattr(request, field)) for field in material):
        raise OrganisationMutationConflict("the edit does not change organisation metadata")
    version = connection.execute(
        text(sql.UPDATE_UNIT), _request_params(command, occurred_at)
    ).scalar_one()
    return OrganisationMutationResult(request.unit_id, int(version), None)


def _locked_unit(connection: Connection, unit_id: UUID) -> RowMapping | None:
    return (
        connection.execute(
            text("SELECT * FROM organisation_units WHERE unit_id=:unit_id FOR UPDATE"),
            {"unit_id": unit_id},
        )
        .mappings()
        .first()
    )


def _require_grant(
    connection: Connection,
    command: OrganisationMutationCommand,
    target_id: UUID,
    action: ManagementAction,
    occurred_at: datetime,
) -> None:
    grant_id = command.request.authorising_grant_id
    lock_lineages(connection, (grant_id,))
    validate_lineage(connection, grant_id, command.actor_user_id, target_id, action, occurred_at)


def _write_command(
    connection: Connection,
    command: OrganisationMutationCommand,
    result: OrganisationMutationResult,
    occurred_at: datetime,
) -> None:
    values = {
        **_request_params(command, occurred_at),
        "request_hash": mutation_hash(command.request, command.actor_user_id),
        "result_version": result.version,
        "topology_revision_id": result.topology_revision_id,
    }
    connection.execute(text(sql.INSERT_COMMAND), values).one()


def _advance_epoch(
    connection: Connection, command: OrganisationMutationCommand, occurred_at: datetime
) -> None:
    connection.execute(
        text(
            "INSERT INTO effective_authority_epochs"
            "(principal_id,scope_unit_id,epoch,advanced_at) VALUES "
            "(:actor_id,:unit_id,1,:occurred_at) ON CONFLICT "
            "(principal_id,scope_unit_id) DO UPDATE SET "
            "epoch=effective_authority_epochs.epoch + 1,advanced_at=EXCLUDED.advanced_at"
        ),
        {
            "actor_id": command.actor_user_id,
            "unit_id": command.request.unit_id,
            "occurred_at": occurred_at,
        },
    )


def _append_evidence(
    connection: Connection,
    command: OrganisationMutationCommand,
    result: OrganisationMutationResult,
    occurred_at: datetime,
) -> None:
    suffix = (
        "created" if command.request.operation is OrganisationMutationOperation.CREATE else "edited"
    )
    event_type = f"organisation_unit_{suffix}"
    values = {
        "event_id": uuid5(NAMESPACE_URL, f"coeus:organisation:{event_type}:{command.command_id}"),
        "event_type": event_type,
        "occurred_at": occurred_at,
        "actor_user_id": str(command.actor_user_id),
        "unit_id": command.request.unit_id,
        "result_version": result.version,
        "payload": json.dumps(
            {
                "unit_id": str(command.request.unit_id),
                "version": result.version,
                "reason_hash": sha256(command.request.reason.encode()).hexdigest(),
            },
            sort_keys=True,
        ),
    }
    connection.execute(text(sql.INSERT_AUDIT), values)
    connection.execute(text(sql.INSERT_OUTBOX), values)


def _request_params(
    command: OrganisationMutationCommand, occurred_at: datetime
) -> dict[str, object]:
    request = command.request
    return {
        **vars(request),
        "operation": request.operation.value,
        "category": request.category.value,
        "command_id": command.command_id,
        "idempotency_key": command.idempotency_key,
        "actor_user_id": command.actor_user_id,
        "occurred_at": occurred_at,
    }


def _uuid(value: object) -> UUID | None:
    return None if value is None else UUID(str(value))
