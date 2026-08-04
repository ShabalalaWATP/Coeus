"""Serialisable PostgreSQL explicit-mapping organisation split store."""

import json
from datetime import datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_merge import MergeUnitVersion
from coeus.domain.organisation_split import (
    OrganisationSplitCommand,
    OrganisationSplitConflict,
    OrganisationSplitIdempotencyConflict,
    OrganisationSplitImpact,
    OrganisationSplitRequest,
    OrganisationSplitResult,
    split_hash,
    validate_split_dispositions,
)
from coeus.persistence import organisation_split_sql as sql
from coeus.persistence.organisation_authority_validation import (
    lock_lineages,
    transaction_time,
    validate_lineage,
)
from coeus.persistence.organisation_split_apply import (
    apply_split_dispositions,
    lock_split_records,
)
from coeus.persistence.organisation_split_evidence import append_split_evidence
from coeus.persistence.organisation_split_inspection import inspect_split
from coeus.persistence.serializable_retry import retry_serializable_once


class PostgresOrganisationSplitStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def inspect(self, request: OrganisationSplitRequest) -> OrganisationSplitImpact:
        with self._engine.begin() as connection:
            return inspect_split(connection, request)

    def replay(self, command: OrganisationSplitCommand) -> OrganisationSplitResult | None:
        with self._engine.begin() as connection:
            return _replay(_load_command(connection, command), command)

    def apply(self, command: OrganisationSplitCommand) -> OrganisationSplitResult:
        return retry_serializable_once(lambda: self._apply_once(command))

    def _apply_once(self, command: OrganisationSplitCommand) -> OrganisationSplitResult:
        with self._engine.begin() as connection:
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
            _locks(connection, command)
            replay = _replay(_load_command(connection, command), command)
            if replay is not None:
                return replay
            lock_split_records(connection, command)
            occurred_at = transaction_time(connection)
            _validate_units_and_authority(connection, command, occurred_at)
            impact = inspect_split(connection, command.plan.request)
            validate_split_dispositions(command.plan, impact)
            if split_hash(command.plan, command.actor_user_id, impact) != command.preview_hash:
                raise OrganisationSplitConflict("the split preview is stale")
            if impact.reservations or impact.team_calendar_events or impact.saved_views:
                raise OrganisationSplitConflict("unsupported dependent records appeared")
            result = _predicted_result(command)
            _write_command(connection, command, result, occurred_at)
            _write_dispositions(connection, command)
            _create_successors(connection, command, occurred_at)
            apply_split_dispositions(connection, command, occurred_at)
            _finish_source_and_parent(connection, command, occurred_at)
            append_split_evidence(connection, command, result, impact, occurred_at)
            return result


def _locks(connection: Connection, command: OrganisationSplitCommand) -> None:
    request = command.plan.request
    values = {
        "coeus:organisation:topology:v1",
        f"idempotency:{command.idempotency_key}",
        f"unit:{request.source.unit_id}",
        f"unit:{request.parent.unit_id}",
        f"grant:{request.source_authorising_grant_id}",
        f"grant:{request.parent_authorising_grant_id}",
        *(f"unit:{item.unit_id}" for item in request.successors),
    }
    for value in sorted(values):
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:value,0))"), {"value": value}
        )
    connection.execute(
        text(
            "SELECT unit_id FROM organisation_units WHERE unit_id IN (:source_id,:parent_id) "
            "OR unit_id=ANY(CAST(:successor_ids AS uuid[])) ORDER BY unit_id FOR UPDATE"
        ),
        {
            "source_id": request.source.unit_id,
            "parent_id": request.parent.unit_id,
            "successor_ids": [str(item.unit_id) for item in request.successors],
        },
    ).all()


def _validate_units_and_authority(
    connection: Connection, command: OrganisationSplitCommand, occurred_at: datetime
) -> None:
    request = command.plan.request
    rows = tuple(
        connection.execute(
            text(
                "SELECT unit_id,version,is_active,parent_unit_id FROM organisation_units "
                "WHERE unit_id IN (:source_id,:parent_id)"
            ),
            {"source_id": request.source.unit_id, "parent_id": request.parent.unit_id},
        ).mappings()
    )
    actual = {UUID(str(row["unit_id"])): row for row in rows}
    source = actual.get(request.source.unit_id)
    parent = actual.get(request.parent.unit_id)
    valid = (
        source is not None
        and parent is not None
        and bool(source["is_active"])
        and bool(parent["is_active"])
        and source["parent_unit_id"] is not None
        and UUID(str(source["parent_unit_id"])) == request.parent.unit_id
        and int(str(source["version"])) == request.source.expected_version
        and int(str(parent["version"])) == request.parent.expected_version
    )
    if not valid:
        raise OrganisationSplitConflict("the split source or parent changed")
    grant_ids = (
        request.source_authorising_grant_id,
        request.parent_authorising_grant_id,
    )
    lock_lineages(connection, grant_ids)
    for unit_id, grant_id in (
        (request.source.unit_id, grant_ids[0]),
        (request.parent.unit_id, grant_ids[1]),
    ):
        validate_lineage(
            connection,
            grant_id,
            command.actor_user_id,
            unit_id,
            ManagementAction.ORGANISATION_RESTRUCTURE,
            occurred_at,
        )


def _predicted_result(command: OrganisationSplitCommand) -> OrganisationSplitResult:
    request = command.plan.request
    return OrganisationSplitResult(
        MergeUnitVersion(request.source.unit_id, request.source.expected_version + 1),
        MergeUnitVersion(request.parent.unit_id, request.parent.expected_version + 1),
        tuple(MergeUnitVersion(item.unit_id, 1) for item in request.successors),
    )


def _create_successors(
    connection: Connection, command: OrganisationSplitCommand, occurred_at: datetime
) -> None:
    request = command.plan.request
    for successor in request.successors:
        values = {
            **vars(successor),
            "category": successor.category.value,
            "parent_id": request.parent.unit_id,
            "occurred_at": occurred_at,
            "command_id": command.command_id,
            "actor_user_id": command.actor_user_id,
            "revision_id": uuid5(
                NAMESPACE_URL,
                f"coeus:organisation:split:successor:{command.command_id}:{successor.unit_id}",
            ),
        }
        connection.execute(text(sql.INSERT_SUCCESSOR), values).one()
        connection.execute(text(sql.INSERT_SELF_CLOSURE), values).one()
        connection.execute(text(sql.INSERT_PARENT_CLOSURE), values).all()
        connection.execute(text(sql.INSERT_SUCCESSOR_REVISION), values).one()


def _finish_source_and_parent(
    connection: Connection, command: OrganisationSplitCommand, occurred_at: datetime
) -> None:
    request = command.plan.request
    connection.execute(
        text(
            "UPDATE organisation_units SET is_active=false,valid_until=:occurred_at,"
            "version=version + 1,updated_at=:occurred_at WHERE unit_id=:unit_id "
            "AND version=:expected_version AND is_active RETURNING version"
        ),
        {
            "unit_id": request.source.unit_id,
            "expected_version": request.source.expected_version,
            "occurred_at": occurred_at,
        },
    ).scalar_one()
    connection.execute(
        text(
            "UPDATE organisation_units SET version=version + 1,updated_at=:occurred_at "
            "WHERE unit_id=:unit_id AND version=:expected_version AND is_active RETURNING version"
        ),
        {
            "unit_id": request.parent.unit_id,
            "expected_version": request.parent.expected_version,
            "occurred_at": occurred_at,
        },
    ).scalar_one()


def _load_command(
    connection: Connection, command: OrganisationSplitCommand
) -> tuple[RowMapping, ...]:
    return tuple(
        connection.execute(
            text(
                "SELECT * FROM organisation_split_commands WHERE command_id=:command_id "
                "OR idempotency_key=:idempotency_key ORDER BY command_id"
            ),
            {"command_id": command.command_id, "idempotency_key": command.idempotency_key},
        ).mappings()
    )


def _replay(
    rows: tuple[RowMapping, ...], command: OrganisationSplitCommand
) -> OrganisationSplitResult | None:
    if not rows:
        return None
    if len(rows) != 1:
        raise OrganisationSplitIdempotencyConflict(
            "command and idempotency key identify different splits"
        )
    row = rows[0]
    request = command.plan.request
    matches = (
        UUID(str(row["command_id"])) == command.command_id
        and str(row["idempotency_key"]) == command.idempotency_key
        and str(row["request_hash"]) == command.preview_hash
        and UUID(str(row["actor_user_id"])) == command.actor_user_id
        and UUID(str(row["source_unit_id"])) == request.source.unit_id
        and UUID(str(row["parent_unit_id"])) == request.parent.unit_id
        and int(str(row["source_expected_version"])) == request.source.expected_version
        and int(str(row["parent_expected_version"])) == request.parent.expected_version
        and str(row["reason_hash"]) == sha256(request.reason.encode()).hexdigest()
    )
    if not matches:
        raise OrganisationSplitIdempotencyConflict(
            "command or idempotency key is already used by another split"
        )
    return OrganisationSplitResult(
        MergeUnitVersion(request.source.unit_id, int(str(row["source_result_version"]))),
        MergeUnitVersion(request.parent.unit_id, int(str(row["parent_result_version"]))),
        tuple(MergeUnitVersion(item.unit_id, 1) for item in request.successors),
        True,
    )


def _write_command(
    connection: Connection,
    command: OrganisationSplitCommand,
    result: OrganisationSplitResult,
    occurred_at: datetime,
) -> None:
    request = command.plan.request
    values = {
        "command_id": command.command_id,
        "idempotency_key": command.idempotency_key,
        "request_hash": command.preview_hash,
        "reason_hash": sha256(request.reason.encode()).hexdigest(),
        "actor_user_id": command.actor_user_id,
        "source_id": request.source.unit_id,
        "parent_id": request.parent.unit_id,
        "source_expected": request.source.expected_version,
        "parent_expected": request.parent.expected_version,
        "source_result": result.source.expected_version,
        "parent_result": result.parent.expected_version,
        "successor_specs": _successor_json(command),
        "source_grant_id": request.source_authorising_grant_id,
        "parent_grant_id": request.parent_authorising_grant_id,
        "occurred_at": occurred_at,
    }
    connection.execute(text(sql.INSERT_COMMAND), values).one()


def _write_dispositions(connection: Connection, command: OrganisationSplitCommand) -> None:
    for item in command.plan.dispositions:
        connection.execute(
            text(sql.INSERT_DISPOSITION),
            {
                "command_id": command.command_id,
                "record_kind": item.kind.value,
                "record_id": item.record_id,
                "expected_version": item.expected_version,
                "action": item.action.value,
                "target_unit_id": item.target_unit_id,
                "replacement_id": item.replacement_id,
            },
        ).one()


def _successor_json(command: OrganisationSplitCommand) -> str:
    return json.dumps(
        [
            {
                **vars(item),
                "unit_id": str(item.unit_id),
                "category": item.category.value,
            }
            for item in command.plan.request.successors
        ],
        sort_keys=True,
    )
