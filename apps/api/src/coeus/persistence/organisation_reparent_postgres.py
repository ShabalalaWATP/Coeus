"""Serialisable PostgreSQL organisation reparent command store."""

import json
from datetime import datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.domain.organisation import MAX_ORGANISATION_DEPTH, ManagementAction
from coeus.domain.organisation_reparent import (
    OrganisationReparentCommand,
    OrganisationReparentConflict,
    OrganisationReparentIdempotencyConflict,
    OrganisationReparentImpact,
    OrganisationReparentRequest,
    OrganisationReparentResult,
    reparent_hash,
)
from coeus.persistence import organisation_reparent_sql as sql
from coeus.persistence.organisation_authority_validation import (
    lock_lineages,
    transaction_time,
    validate_lineage,
)
from coeus.persistence.organisation_reparent_evidence import advance_epochs, append_evidence
from coeus.persistence.serializable_retry import retry_serializable_once


class PostgresOrganisationReparentStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def inspect(self, request: OrganisationReparentRequest) -> OrganisationReparentImpact:
        with self._engine.begin() as connection:
            return _impact(connection, request)

    def replay(self, command: OrganisationReparentCommand) -> OrganisationReparentResult | None:
        with self._engine.begin() as connection:
            return _replay(_load_command(connection, command), command)

    def apply(self, command: OrganisationReparentCommand) -> OrganisationReparentResult:
        return retry_serializable_once(lambda: self._apply_once(command))

    def _apply_once(self, command: OrganisationReparentCommand) -> OrganisationReparentResult:
        with self._engine.begin() as connection:
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
            _locks(connection, command)
            replay = _replay(_load_command(connection, command), command)
            if replay is not None:
                return replay
            occurred_at = transaction_time(connection)
            impact = _validate_and_impact(connection, command, occurred_at)
            if (
                reparent_hash(command.request, command.actor_user_id, impact)
                != command.preview_hash
            ):
                raise OrganisationReparentConflict("the reparent preview is stale")
            predicted = _predicted_result(command)
            _write_command(connection, command, impact, predicted, occurred_at)
            result = _move(connection, command, occurred_at)
            advance_epochs(connection, command, impact, occurred_at)
            append_evidence(connection, command, impact, result, occurred_at)
            return result


def _locks(connection: Connection, command: OrganisationReparentCommand) -> None:
    request = command.request
    values = (
        "coeus:organisation:topology:v1",
        f"grant:{request.authorising_grant_id}",
        f"idempotency:{command.idempotency_key}",
    )
    for value in sorted(values):
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:value, 0))"), {"value": value}
        )
    connection.execute(
        text(sql.LOCK_UNITS),
        {"unit_id": request.unit_id, "new_parent_unit_id": request.new_parent_unit_id},
    ).all()


def _load_command(
    connection: Connection, command: OrganisationReparentCommand
) -> tuple[RowMapping, ...]:
    return tuple(
        connection.execute(
            text(sql.LOAD_COMMAND),
            {"command_id": command.command_id, "idempotency_key": command.idempotency_key},
        ).mappings()
    )


def _replay(
    rows: tuple[RowMapping, ...], command: OrganisationReparentCommand
) -> OrganisationReparentResult | None:
    if not rows:
        return None
    if len(rows) != 1:
        raise OrganisationReparentIdempotencyConflict(
            "command and idempotency key identify different reparent operations"
        )
    row = rows[0]
    request = command.request
    matches = (
        UUID(str(row["command_id"])) == command.command_id
        and str(row["idempotency_key"]) == command.idempotency_key
        and str(row["request_hash"]) == command.preview_hash
        and UUID(str(row["actor_user_id"])) == command.actor_user_id
        and UUID(str(row["unit_id"])) == request.unit_id
        and UUID(str(row["new_parent_unit_id"])) == request.new_parent_unit_id
        and UUID(str(row["authorising_grant_id"])) == request.authorising_grant_id
        and int(str(row["expected_unit_version"])) == request.expected_unit_version
        and int(str(row["expected_parent_version"])) == request.expected_parent_version
        and str(row["reason_hash"]) == sha256(request.reason.encode()).hexdigest()
    )
    if not matches:
        raise OrganisationReparentIdempotencyConflict(
            "command or idempotency key is already used by another reparent operation"
        )
    return OrganisationReparentResult(
        request.unit_id,
        request.new_parent_unit_id,
        int(str(row["result_version"])),
        UUID(str(row["topology_revision_id"])),
        True,
    )


def _validate_and_impact(
    connection: Connection, command: OrganisationReparentCommand, occurred_at: datetime
) -> OrganisationReparentImpact:
    request = command.request
    source = _unit(connection, request.unit_id)
    target = _unit(connection, request.new_parent_unit_id)
    if source is None or not bool(source["is_active"]) or source["parent_unit_id"] is None:
        raise OrganisationReparentConflict("the source unit cannot be reparented")
    if int(str(source["version"])) != request.expected_unit_version:
        raise OrganisationReparentConflict("the organisation unit version is stale")
    if target is None or not bool(target["is_active"]):
        raise OrganisationReparentConflict("the new parent unit is not active")
    if int(str(target["version"])) != request.expected_parent_version:
        raise OrganisationReparentConflict("the new parent unit version is stale")
    if UUID(str(source["parent_unit_id"])) == request.new_parent_unit_id:
        raise OrganisationReparentConflict("the unit already has this parent")
    cycle = connection.execute(
        text(
            "SELECT 1 FROM organisation_unit_closure WHERE ancestor_unit_id=:unit_id "
            "AND descendant_unit_id=:new_parent_unit_id"
        ),
        vars(request),
    ).first()
    if cycle is not None:
        raise OrganisationReparentConflict("the new parent would create a cycle")
    lock_lineages(connection, (request.authorising_grant_id,))
    for unit_id in (request.unit_id, request.new_parent_unit_id):
        validate_lineage(
            connection,
            request.authorising_grant_id,
            command.actor_user_id,
            unit_id,
            ManagementAction.ORGANISATION_REPARENT,
            occurred_at,
        )
    impact = _impact(connection, request)
    if impact.maximum_result_depth > MAX_ORGANISATION_DEPTH:
        raise OrganisationReparentConflict("the organisation depth limit would be exceeded")
    if impact.newly_covering_grants:
        raise OrganisationReparentConflict(
            "reparenting would silently broaden one or more management grants"
        )
    return impact


def _impact(
    connection: Connection, request: OrganisationReparentRequest
) -> OrganisationReparentImpact:
    row = connection.execute(text(sql.IMPACT), vars(request)).mappings().first()
    if row is None or row["parent_unit_id"] is None or row["revision_id"] is None:
        raise OrganisationReparentConflict("the reparent topology is incomplete")
    state = {
        key: str(row[key])
        for key in (
            "parent_unit_id",
            "revision_id",
            "subtree_state",
            "grant_state",
            "membership_state",
            "capability_state",
            "task_state",
            "source_version",
            "parent_version",
            "source_active",
            "parent_active",
        )
    }
    digest = sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
    return OrganisationReparentImpact(
        UUID(str(row["parent_unit_id"])),
        UUID(str(row["revision_id"])),
        int(str(row["descendants"])),
        int(str(row["memberships"])),
        int(str(row["grants"])),
        int(str(row["capability_mappings"])),
        int(str(row["active_task_legs"])),
        0,
        0,
        0,
        0,
        int(str(row["newly_covering_grants"])),
        int(str(row["maximum_result_depth"])),
        digest,
    )


def _unit(connection: Connection, unit_id: UUID) -> RowMapping | None:
    return (
        connection.execute(
            text("SELECT * FROM organisation_units WHERE unit_id=:unit_id FOR UPDATE"),
            {"unit_id": unit_id},
        )
        .mappings()
        .first()
    )


def _move(
    connection: Connection,
    command: OrganisationReparentCommand,
    occurred_at: datetime,
) -> OrganisationReparentResult:
    params = {**vars(command.request), **vars(command), "occurred_at": occurred_at}
    connection.execute(
        text("SELECT set_config('coeus.organisation_reparent_command',:command_id,true)"),
        {"command_id": str(command.command_id)},
    )
    version = connection.execute(text(sql.UPDATE_PARENT), params).scalar_one()
    connection.execute(text(sql.DELETE_EXTERNAL_CLOSURE), params)
    connection.execute(text(sql.INSERT_EXTERNAL_CLOSURE), params)
    root_revision_id: UUID | None = None
    for row in connection.execute(text(sql.LOAD_REVISION_PATHS), params).mappings():
        unit_id = UUID(str(row["unit_id"]))
        revision_id = uuid5(
            NAMESPACE_URL, f"coeus:organisation:reparent:revision:{command.command_id}:{unit_id}"
        )
        revision_params = {
            **params,
            "revision_id": revision_id,
            "revision_unit_id": unit_id,
            "revision_parent_unit_id": row["parent_unit_id"],
            "path": row["path"],
        }
        connection.execute(text(sql.INSERT_REVISION), revision_params).one()
        if unit_id == command.request.unit_id:
            root_revision_id = revision_id
    if root_revision_id is None:
        raise OrganisationReparentConflict("the moved subtree has no topology revision")
    return OrganisationReparentResult(
        command.request.unit_id,
        command.request.new_parent_unit_id,
        int(version),
        root_revision_id,
    )


def _predicted_result(command: OrganisationReparentCommand) -> OrganisationReparentResult:
    request = command.request
    revision_id = uuid5(
        NAMESPACE_URL,
        f"coeus:organisation:reparent:revision:{command.command_id}:{request.unit_id}",
    )
    return OrganisationReparentResult(
        request.unit_id,
        request.new_parent_unit_id,
        request.expected_unit_version + 1,
        revision_id,
    )


def _write_command(
    connection: Connection,
    command: OrganisationReparentCommand,
    impact: OrganisationReparentImpact,
    result: OrganisationReparentResult,
    occurred_at: datetime,
) -> None:
    values = {
        **vars(command.request),
        **vars(command),
        "request_hash": command.preview_hash,
        "reason_hash": sha256(command.request.reason.encode()).hexdigest(),
        "source_parent_unit_id": impact.source_parent_unit_id,
        "result_version": result.version,
        "topology_revision_id": result.topology_revision_id,
        "occurred_at": occurred_at,
    }
    connection.execute(text(sql.INSERT_COMMAND), values).one()
