"""Serialisable PostgreSQL explicit-disposition organisation merge store."""

import json
from datetime import datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.domain.organisation import MAX_ORGANISATION_DEPTH, ManagementAction
from coeus.domain.organisation_merge import (
    MergeUnitVersion,
    OrganisationMergeCommand,
    OrganisationMergeConflict,
    OrganisationMergeIdempotencyConflict,
    OrganisationMergeImpact,
    OrganisationMergeRequest,
    OrganisationMergeResult,
    merge_hash,
    validate_merge_dispositions,
)
from coeus.persistence import organisation_merge_sql as sql
from coeus.persistence.organisation_authority_validation import (
    lock_lineages,
    transaction_time,
    validate_lineage,
)
from coeus.persistence.organisation_merge_apply import (
    apply_dispositions,
    lock_merge_records,
)
from coeus.persistence.organisation_merge_inspection import inspect_merge
from coeus.persistence.serializable_retry import retry_serializable_once


class PostgresOrganisationMergeStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def inspect(self, request: OrganisationMergeRequest) -> OrganisationMergeImpact:
        with self._engine.begin() as connection:
            return inspect_merge(connection, request)

    def replay(self, command: OrganisationMergeCommand) -> OrganisationMergeResult | None:
        with self._engine.begin() as connection:
            return _replay(_load_command(connection, command), command)

    def apply(self, command: OrganisationMergeCommand) -> OrganisationMergeResult:
        return retry_serializable_once(lambda: self._apply_once(command))

    def _apply_once(self, command: OrganisationMergeCommand) -> OrganisationMergeResult:
        with self._engine.begin() as connection:
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
            _advisory_locks(connection, command)
            replay = _replay(_load_command(connection, command), command)
            if replay is not None:
                return replay
            _lock_units(connection, command)
            lock_merge_records(connection, command)
            occurred_at = transaction_time(connection)
            _validate_units_and_authority(connection, command, occurred_at)
            impact = inspect_merge(connection, command.plan.request)
            validate_merge_dispositions(command.plan, impact)
            expected_hash = merge_hash(command.plan, command.actor_user_id, impact)
            if expected_hash != command.preview_hash:
                raise OrganisationMergeConflict("the merge preview is stale")
            if impact.maximum_result_depth > MAX_ORGANISATION_DEPTH:
                raise OrganisationMergeConflict("the merged hierarchy would exceed maximum depth")
            if impact.newly_covering_grants:
                raise OrganisationMergeConflict("the merge would silently broaden a grant")
            if impact.reservations or impact.team_calendar_events or impact.saved_views:
                raise OrganisationMergeConflict("unsupported dependent records appeared")
            predicted = _predicted_result(command)
            _write_command(connection, command, predicted, occurred_at)
            _write_dispositions(connection, command)
            apply_dispositions(connection, command, occurred_at)
            result = _finish_units(connection, command, occurred_at)
            _append_evidence(connection, command, result, impact, occurred_at)
            return result


def _advisory_locks(connection: Connection, command: OrganisationMergeCommand) -> None:
    request = command.plan.request
    values = {
        "coeus:organisation:topology:v1",
        f"idempotency:{command.idempotency_key}",
        *(f"unit:{item.unit_id}" for item in (*request.sources, request.successor)),
        *(f"grant:{item.grant_id}" for item in request.authorities),
    }
    for value in sorted(values):
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:value, 0))"), {"value": value}
        )


def _lock_units(connection: Connection, command: OrganisationMergeCommand) -> None:
    request = command.plan.request
    ids = [str(item.unit_id) for item in (*request.sources, request.successor)]
    connection.execute(
        text(
            "SELECT unit_id FROM organisation_units WHERE unit_id=ANY(CAST(:ids AS uuid[])) "
            "ORDER BY unit_id FOR UPDATE"
        ),
        {"ids": ids},
    ).all()


def _validate_units_and_authority(
    connection: Connection, command: OrganisationMergeCommand, occurred_at: datetime
) -> None:
    request = command.plan.request
    expected = {
        item.unit_id: item.expected_version for item in (*request.sources, request.successor)
    }
    rows = connection.execute(
        text(
            "SELECT unit_id,version,is_active,parent_unit_id FROM organisation_units "
            "WHERE unit_id=ANY(CAST(:ids AS uuid[]))"
        ),
        {"ids": [str(item) for item in expected]},
    ).mappings()
    actual = {UUID(str(row["unit_id"])): row for row in rows}
    if len(actual) != len(expected) or any(
        not bool(actual[unit_id]["is_active"]) or int(str(actual[unit_id]["version"])) != version
        for unit_id, version in expected.items()
    ):
        raise OrganisationMergeConflict("an affected organisation unit changed")
    if any(actual[item.unit_id]["parent_unit_id"] is None for item in request.sources):
        raise OrganisationMergeConflict("a root organisation unit cannot be merged")
    nested_successor = connection.execute(
        text(
            "SELECT 1 FROM organisation_unit_closure WHERE "
            "ancestor_unit_id=ANY(CAST(:source_ids AS uuid[])) "
            "AND descendant_unit_id=:successor_id LIMIT 1"
        ),
        {
            "source_ids": [str(item.unit_id) for item in request.sources],
            "successor_id": request.successor.unit_id,
        },
    ).first()
    if nested_successor is not None:
        raise OrganisationMergeConflict("the successor cannot be inside a source subtree")
    overlapping_sources = connection.execute(
        text(
            "SELECT 1 FROM organisation_unit_closure WHERE depth>0 "
            "AND ancestor_unit_id=ANY(CAST(:source_ids AS uuid[])) "
            "AND descendant_unit_id=ANY(CAST(:source_ids AS uuid[])) LIMIT 1"
        ),
        {"source_ids": [str(item.unit_id) for item in request.sources]},
    ).first()
    if overlapping_sources is not None:
        raise OrganisationMergeConflict("merge source subtrees cannot overlap")
    authority = {item.unit_id: item.grant_id for item in request.authorities}
    lock_lineages(connection, tuple(authority.values()))
    for unit_id, grant_id in authority.items():
        validate_lineage(
            connection,
            grant_id,
            command.actor_user_id,
            unit_id,
            ManagementAction.ORGANISATION_RESTRUCTURE,
            occurred_at,
        )


def _finish_units(
    connection: Connection, command: OrganisationMergeCommand, occurred_at: datetime
) -> OrganisationMergeResult:
    request = command.plan.request
    source_rows = connection.execute(
        text(
            "UPDATE organisation_units SET is_active=false,valid_until=:occurred_at,"
            "version=version + 1,updated_at=:occurred_at "
            "WHERE unit_id=ANY(CAST(:source_ids AS uuid[])) AND is_active "
            "RETURNING unit_id,version"
        ),
        {"source_ids": [str(item.unit_id) for item in request.sources], "occurred_at": occurred_at},
    ).mappings()
    source_versions = {UUID(str(row["unit_id"])): int(str(row["version"])) for row in source_rows}
    if len(source_versions) != len(request.sources):
        raise OrganisationMergeConflict("a source unit changed before deactivation")
    successor_version = connection.execute(
        text(
            "UPDATE organisation_units SET version=version + 1,updated_at=:occurred_at "
            "WHERE unit_id=:unit_id AND version=:expected_version AND is_active RETURNING version"
        ),
        {
            "unit_id": request.successor.unit_id,
            "expected_version": request.successor.expected_version,
            "occurred_at": occurred_at,
        },
    ).scalar_one_or_none()
    if successor_version is None:
        raise OrganisationMergeConflict("the successor unit changed")
    ordered = tuple(
        MergeUnitVersion(item.unit_id, source_versions[item.unit_id]) for item in request.sources
    )
    return OrganisationMergeResult(request.successor.unit_id, int(successor_version), ordered)


def _predicted_result(command: OrganisationMergeCommand) -> OrganisationMergeResult:
    request = command.plan.request
    return OrganisationMergeResult(
        request.successor.unit_id,
        request.successor.expected_version + 1,
        tuple(
            MergeUnitVersion(item.unit_id, item.expected_version + 1) for item in request.sources
        ),
    )


def _load_command(
    connection: Connection, command: OrganisationMergeCommand
) -> tuple[RowMapping, ...]:
    return tuple(
        connection.execute(
            text(
                "SELECT * FROM organisation_merge_commands "
                "WHERE command_id=:command_id OR idempotency_key=:idempotency_key "
                "ORDER BY command_id"
            ),
            {"command_id": command.command_id, "idempotency_key": command.idempotency_key},
        ).mappings()
    )


def _replay(
    rows: tuple[RowMapping, ...], command: OrganisationMergeCommand
) -> OrganisationMergeResult | None:
    if not rows:
        return None
    if len(rows) != 1:
        raise OrganisationMergeIdempotencyConflict(
            "command and idempotency key identify different merges"
        )
    row = rows[0]
    request = command.plan.request
    source_ids = tuple(UUID(str(item)) for item in row["source_unit_ids"])
    source_expected = tuple(int(item) for item in row["source_expected_versions"])
    matches = (
        UUID(str(row["command_id"])) == command.command_id
        and str(row["idempotency_key"]) == command.idempotency_key
        and str(row["request_hash"]) == command.preview_hash
        and UUID(str(row["actor_user_id"])) == command.actor_user_id
        and source_ids == tuple(item.unit_id for item in request.sources)
        and source_expected == tuple(item.expected_version for item in request.sources)
        and UUID(str(row["successor_unit_id"])) == request.successor.unit_id
        and int(str(row["successor_expected_version"])) == request.successor.expected_version
        and str(row["reason_hash"]) == sha256(request.reason.encode()).hexdigest()
    )
    if not matches:
        raise OrganisationMergeIdempotencyConflict(
            "command or idempotency key is already used by another merge"
        )
    results = tuple(int(item) for item in row["source_result_versions"])
    return OrganisationMergeResult(
        request.successor.unit_id,
        int(str(row["successor_result_version"])),
        tuple(
            MergeUnitVersion(unit_id, version)
            for unit_id, version in zip(source_ids, results, strict=True)
        ),
        True,
    )


def _write_command(
    connection: Connection,
    command: OrganisationMergeCommand,
    result: OrganisationMergeResult,
    occurred_at: datetime,
) -> None:
    request = command.plan.request
    values = {
        "command_id": command.command_id,
        "idempotency_key": command.idempotency_key,
        "request_hash": command.preview_hash,
        "reason_hash": sha256(request.reason.encode()).hexdigest(),
        "actor_user_id": command.actor_user_id,
        "source_ids": [str(item.unit_id) for item in request.sources],
        "source_expected": [item.expected_version for item in request.sources],
        "source_results": [item.expected_version for item in result.source_versions],
        "successor_id": request.successor.unit_id,
        "successor_expected": request.successor.expected_version,
        "successor_result": result.successor_version,
        "authority_map": json.dumps(
            {str(item.unit_id): str(item.grant_id) for item in request.authorities}, sort_keys=True
        ),
        "occurred_at": occurred_at,
    }
    connection.execute(text(sql.INSERT_COMMAND), values).one()


def _write_dispositions(connection: Connection, command: OrganisationMergeCommand) -> None:
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


def _append_evidence(
    connection: Connection,
    command: OrganisationMergeCommand,
    result: OrganisationMergeResult,
    impact: OrganisationMergeImpact,
    occurred_at: datetime,
) -> None:
    request = command.plan.request
    source_ids = [str(item.unit_id) for item in request.sources]
    connection.execute(
        text(sql.ADVANCE_EPOCHS),
        {
            "source_ids": source_ids,
            "successor_id": result.successor_unit_id,
            "occurred_at": occurred_at,
        },
    )
    event_id = uuid5(NAMESPACE_URL, f"coeus:organisation:merged:{command.command_id}")
    payload = json.dumps(
        {
            "source_unit_ids": source_ids,
            "successor_unit_id": str(result.successor_unit_id),
            "successor_version": result.successor_version,
            "disposition_count": len(command.plan.dispositions),
            "state_digest": impact.state_digest,
            "reason_hash": sha256(request.reason.encode()).hexdigest(),
        },
        sort_keys=True,
    )
    values = {
        "event_id": event_id,
        "event_type": "organisation_units_merged",
        "occurred_at": occurred_at,
        "actor_user_id": str(command.actor_user_id),
        "aggregate_id": result.successor_unit_id,
        "aggregate_version": result.successor_version,
        "payload": payload,
    }
    connection.execute(text(sql.INSERT_AUDIT), values)
    connection.execute(text(sql.INSERT_OUTBOX), values)
