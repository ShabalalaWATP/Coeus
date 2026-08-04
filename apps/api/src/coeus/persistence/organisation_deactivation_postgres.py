"""Serialisable PostgreSQL organisation unit deactivation store."""

import json
from datetime import datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_deactivation import (
    OrganisationDeactivationCommand,
    OrganisationDeactivationConflict,
    OrganisationDeactivationIdempotencyConflict,
    OrganisationDeactivationImpact,
    OrganisationDeactivationRequest,
    OrganisationDeactivationResult,
    deactivation_hash,
)
from coeus.persistence import organisation_deactivation_sql as sql
from coeus.persistence.organisation_authority_validation import (
    lock_lineages,
    transaction_time,
    validate_lineage,
)
from coeus.persistence.serializable_retry import retry_serializable_once


class PostgresOrganisationDeactivationStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def inspect(self, request: OrganisationDeactivationRequest) -> OrganisationDeactivationImpact:
        with self._engine.begin() as connection:
            return _impact(connection, request)

    def replay(
        self, command: OrganisationDeactivationCommand
    ) -> OrganisationDeactivationResult | None:
        with self._engine.begin() as connection:
            return _replay(_load_command(connection, command), command)

    def apply(self, command: OrganisationDeactivationCommand) -> OrganisationDeactivationResult:
        return retry_serializable_once(lambda: self._apply_once(command))

    def _apply_once(
        self, command: OrganisationDeactivationCommand
    ) -> OrganisationDeactivationResult:
        with self._engine.begin() as connection:
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
            _locks(connection, command)
            replay = _replay(_load_command(connection, command), command)
            if replay is not None:
                return replay
            occurred_at = transaction_time(connection)
            request = command.request
            unit = (
                connection.execute(
                    text("SELECT * FROM organisation_units WHERE unit_id=:unit_id FOR UPDATE"),
                    vars(request),
                )
                .mappings()
                .first()
            )
            valid = (
                unit is not None
                and bool(unit["is_active"])
                and unit["parent_unit_id"] is not None
                and int(str(unit["version"])) == request.expected_version
            )
            if not valid:
                raise OrganisationDeactivationConflict("the organisation unit changed")
            lock_lineages(connection, (request.authorising_grant_id,))
            validate_lineage(
                connection,
                request.authorising_grant_id,
                command.actor_user_id,
                request.unit_id,
                ManagementAction.ORGANISATION_RESTRUCTURE,
                occurred_at,
            )
            impact = _impact(connection, request)
            if deactivation_hash(request, command.actor_user_id, impact) != command.preview_hash:
                raise OrganisationDeactivationConflict("the deactivation preview is stale")
            if impact.blocking_count:
                raise OrganisationDeactivationConflict(
                    "the organisation unit still has dependent records requiring disposition"
                )
            version = connection.execute(
                text(sql.DEACTIVATE), {**vars(request), "occurred_at": occurred_at}
            ).scalar_one()
            result = OrganisationDeactivationResult(request.unit_id, int(version))
            _write_command(connection, command, result, occurred_at)
            _append_evidence(connection, command, result, occurred_at)
            return result


def _locks(connection: Connection, command: OrganisationDeactivationCommand) -> None:
    request = command.request
    for value in sorted(
        (
            "coeus:organisation:topology:v1",
            f"grant:{request.authorising_grant_id}",
            f"idempotency:{command.idempotency_key}",
            f"unit:{request.unit_id}",
        )
    ):
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:value, 0))"), {"value": value}
        )


def _load_command(
    connection: Connection, command: OrganisationDeactivationCommand
) -> tuple[RowMapping, ...]:
    return tuple(
        connection.execute(
            text(sql.LOAD_COMMAND),
            {"command_id": command.command_id, "idempotency_key": command.idempotency_key},
        ).mappings()
    )


def _replay(
    rows: tuple[RowMapping, ...], command: OrganisationDeactivationCommand
) -> OrganisationDeactivationResult | None:
    if not rows:
        return None
    if len(rows) != 1:
        raise OrganisationDeactivationIdempotencyConflict(
            "command and idempotency key identify different deactivations"
        )
    row = rows[0]
    request = command.request
    matches = (
        UUID(str(row["command_id"])) == command.command_id
        and str(row["idempotency_key"]) == command.idempotency_key
        and str(row["request_hash"]) == command.preview_hash
        and UUID(str(row["actor_user_id"])) == command.actor_user_id
        and UUID(str(row["unit_id"])) == request.unit_id
        and UUID(str(row["authorising_grant_id"])) == request.authorising_grant_id
        and int(str(row["expected_version"])) == request.expected_version
        and str(row["reason_hash"]) == sha256(request.reason.encode()).hexdigest()
    )
    if not matches:
        raise OrganisationDeactivationIdempotencyConflict(
            "command or idempotency key is already used by another deactivation"
        )
    return OrganisationDeactivationResult(request.unit_id, int(str(row["result_version"])), True)


def _impact(
    connection: Connection, request: OrganisationDeactivationRequest
) -> OrganisationDeactivationImpact:
    row = connection.execute(text(sql.IMPACT), vars(request)).mappings().first()
    if row is None:
        raise OrganisationDeactivationConflict("the organisation unit is unavailable")
    names = (
        "active_children",
        "active_descendants",
        "memberships",
        "direct_grants",
        "delivery_profiles",
        "capability_mappings",
        "active_task_legs",
        "pending_transfers",
    )
    counts = {name: int(str(row[name])) for name in names}
    state = {
        "version": str(row["version"]),
        "is_active": str(row["is_active"]),
        "parent_unit_id": str(row["parent_unit_id"]),
        "subtree_state": str(row["subtree_state"]),
        "membership_state": str(row["membership_state"]),
        "grant_state": str(row["grant_state"]),
        **counts,
    }
    digest = sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
    return OrganisationDeactivationImpact(
        counts["active_children"],
        counts["active_descendants"],
        counts["memberships"],
        counts["direct_grants"],
        counts["delivery_profiles"],
        counts["capability_mappings"],
        counts["active_task_legs"],
        0,
        0,
        counts["pending_transfers"],
        0,
        digest,
    )


def _write_command(
    connection: Connection,
    command: OrganisationDeactivationCommand,
    result: OrganisationDeactivationResult,
    occurred_at: datetime,
) -> None:
    request = command.request
    values = {
        **vars(request),
        "command_id": command.command_id,
        "idempotency_key": command.idempotency_key,
        "actor_user_id": command.actor_user_id,
        "request_hash": command.preview_hash,
        "reason_hash": sha256(request.reason.encode()).hexdigest(),
        "result_version": result.version,
        "occurred_at": occurred_at,
    }
    connection.execute(text(sql.INSERT_COMMAND), values).one()


def _append_evidence(
    connection: Connection,
    command: OrganisationDeactivationCommand,
    result: OrganisationDeactivationResult,
    occurred_at: datetime,
) -> None:
    request = command.request
    connection.execute(
        text(
            "INSERT INTO effective_authority_epochs(principal_id,scope_unit_id,epoch,advanced_at) "
            "SELECT DISTINCT manager_user_id,root_unit_id,1,:occurred_at "
            "FROM team_management_grants WHERE root_unit_id IN (SELECT ancestor_unit_id "
            "FROM organisation_unit_closure WHERE descendant_unit_id=:unit_id) "
            "ON CONFLICT (principal_id,scope_unit_id) DO UPDATE SET "
            "epoch=effective_authority_epochs.epoch + 1,advanced_at=EXCLUDED.advanced_at"
        ),
        {"unit_id": request.unit_id, "occurred_at": occurred_at},
    )
    event_id = uuid5(NAMESPACE_URL, f"coeus:organisation:deactivated:{command.command_id}")
    payload = json.dumps(
        {
            "unit_id": str(request.unit_id),
            "version": result.version,
            "reason_hash": sha256(request.reason.encode()).hexdigest(),
        },
        sort_keys=True,
    )
    values = {
        "event_id": event_id,
        "event_type": "organisation_unit_deactivated",
        "occurred_at": occurred_at,
        "actor_user_id": str(command.actor_user_id),
        "unit_id": request.unit_id,
        "version": result.version,
        "payload": payload,
    }
    connection.execute(text(_INSERT_AUDIT), values)
    connection.execute(text(_INSERT_OUTBOX), values)


_INSERT_AUDIT = """
INSERT INTO coeus_audit_events(event_id,event_type,occurred_at,actor_user_id,metadata)
VALUES (:event_id,:event_type,:occurred_at,:actor_user_id,CAST(:payload AS jsonb))
ON CONFLICT (event_id) DO NOTHING
"""

_INSERT_OUTBOX = """
INSERT INTO coeus_outbox(event_id,aggregate_id,aggregate_version,event_type,payload)
VALUES (:event_id,:unit_id,:version,:event_type,CAST(:payload AS jsonb))
ON CONFLICT (aggregate_id,aggregate_version,event_type) DO NOTHING
"""
