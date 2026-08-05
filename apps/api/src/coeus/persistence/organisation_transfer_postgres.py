"""Serialisable PostgreSQL scheduled personnel transfer store."""

import json
from datetime import datetime
from hashlib import sha256
from typing import cast

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.domain.organisation import ManagementAction, OrganisationCategory
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.organisation_transfer import (
    PersonnelTransferCommand,
    PersonnelTransferConflict,
    PersonnelTransferDenied,
    PersonnelTransferImpact,
    PersonnelTransferRequest,
    PersonnelTransferResult,
    PersonnelTransferStatus,
    personnel_transfer_hash,
)
from coeus.persistence import organisation_transfer_sql as sql
from coeus.persistence.organisation_authority_validation import (
    lock_lineages,
    transaction_time,
    validate_lineage,
)
from coeus.persistence.organisation_transfer_evidence import append_transfer_evidence
from coeus.persistence.organisation_transfer_rows import decode_command, replay
from coeus.persistence.serializable_retry import retry_serializable_once

_FAILURE_CODES = frozenset({"account_inactive", "authority_lost", "state_changed"})


class PostgresOrganisationTransferStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def inspect(self, request: PersonnelTransferRequest) -> PersonnelTransferImpact:
        with self._engine.begin() as connection:
            return _impact(connection, request)

    def replay(self, command: PersonnelTransferCommand) -> PersonnelTransferResult | None:
        with self._engine.begin() as connection:
            return replay(_load_command(connection, command), command)

    def apply(self, command: PersonnelTransferCommand) -> PersonnelTransferResult:
        return retry_serializable_once(lambda: self._schedule_once(command))

    def due(
        self, effective_at: datetime, *, limit: int = 100
    ) -> tuple[PersonnelTransferCommand, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between one and 100")
        with self._engine.begin() as connection:
            rows = connection.execute(
                text(sql.LOAD_DUE), {"effective_at": effective_at, "limit": limit}
            ).mappings()
            return tuple(decode_command(row) for row in rows)

    def activate(self, command: PersonnelTransferCommand) -> PersonnelTransferResult:
        return retry_serializable_once(lambda: self._activate_once(command))

    def block(
        self, command: PersonnelTransferCommand, failure_code: str
    ) -> PersonnelTransferResult:
        if failure_code not in _FAILURE_CODES:
            raise ValueError("unsupported personnel transfer failure code")
        with self._engine.begin() as connection:
            row = _locked_transfer(connection, command)
            existing = cast(PersonnelTransferResult, replay((row,), command))
            if existing.status is not PersonnelTransferStatus.PENDING:
                return existing
            occurred_at = transaction_time(connection)
            connection.execute(
                text(sql.MARK_BLOCKED),
                {"command_id": command.command_id, "failure_code": failure_code},
            ).one()
            result = PersonnelTransferResult(
                command.command_id,
                command.request.source_membership_id,
                command.request.target_membership_id,
                PersonnelTransferStatus.BLOCKED,
                command.request.expected_membership_version,
                0,
                failure_code=failure_code,
            )
            append_transfer_evidence(connection, command, result, occurred_at)
            return result

    def _schedule_once(self, command: PersonnelTransferCommand) -> PersonnelTransferResult:
        with self._engine.begin() as connection:
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
            _locks(connection, command)
            existing = replay(_load_command(connection, command), command)
            if existing is not None:
                return existing
            occurred_at = transaction_time(connection)
            if command.request.effective_at <= occurred_at:
                raise PersonnelTransferConflict("a new transfer boundary must be in the future")
            _validate(connection, command, occurred_at)
            pending = connection.execute(
                text(
                    "SELECT 1 FROM organisation_personnel_transfers "
                    "WHERE source_membership_id=:source_membership_id AND status='pending'"
                ),
                vars(command.request),
            ).first()
            if pending is not None:
                raise PersonnelTransferConflict(
                    "the source membership already has a pending transfer"
                )
            values = _values(command, occurred_at)
            connection.execute(text(sql.INSERT_TRANSFER), values).one()
            result = PersonnelTransferResult(
                command.command_id,
                command.request.source_membership_id,
                command.request.target_membership_id,
                PersonnelTransferStatus.PENDING,
                command.request.expected_membership_version,
                0,
            )
            append_transfer_evidence(connection, command, result, occurred_at)
            return result

    def _activate_once(self, command: PersonnelTransferCommand) -> PersonnelTransferResult:
        with self._engine.begin() as connection:
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
            _locks(connection, command)
            row = _locked_transfer(connection, command)
            existing = cast(PersonnelTransferResult, replay((row,), command))
            if existing.status is not PersonnelTransferStatus.PENDING:
                return existing
            occurred_at = transaction_time(connection)
            if command.request.effective_at > occurred_at:
                raise PersonnelTransferConflict("the personnel transfer is not due")
            _validate(connection, command, occurred_at)
            values = _values(command, occurred_at)
            source_version = connection.execute(text(sql.END_SOURCE), values).scalar_one_or_none()
            if source_version is None:
                raise PersonnelTransferConflict("the source membership changed before activation")
            target_version = connection.execute(text(sql.INSERT_TARGET), values).scalar_one()
            values.update(
                source_result_version=int(source_version), target_result_version=int(target_version)
            )
            connection.execute(text(sql.MARK_APPLIED), values).one()
            result = PersonnelTransferResult(
                command.command_id,
                command.request.source_membership_id,
                command.request.target_membership_id,
                PersonnelTransferStatus.APPLIED,
                int(source_version),
                int(target_version),
            )
            append_transfer_evidence(connection, command, result, occurred_at)
            return result


def _locks(connection: Connection, command: PersonnelTransferCommand) -> None:
    request = command.request
    values = {
        f"grant:{request.source_authorising_grant_id}",
        f"grant:{request.target_authorising_grant_id}",
        f"idempotency:{command.idempotency_key}",
        f"user-membership:{request.user_id}",
    }
    for value in sorted(values):
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:value, 0))"), {"value": value}
        )
    connection.execute(text(sql.LOCK_MEMBERSHIPS), vars(request)).all()


def _load_command(
    connection: Connection, command: PersonnelTransferCommand
) -> tuple[RowMapping, ...]:
    return tuple(
        connection.execute(
            text(sql.LOAD_COMMAND),
            {"command_id": command.command_id, "idempotency_key": command.idempotency_key},
        ).mappings()
    )


def _locked_transfer(connection: Connection, command: PersonnelTransferCommand) -> RowMapping:
    row = (
        connection.execute(text(sql.LOCK_TRANSFER), {"command_id": command.command_id})
        .mappings()
        .first()
    )
    if row is None:
        raise PersonnelTransferConflict("the personnel transfer is unavailable")
    return row


def _validate(
    connection: Connection, command: PersonnelTransferCommand, occurred_at: datetime
) -> None:
    request = command.request
    impact = _impact(connection, request)
    if personnel_transfer_hash(request, command.actor_user_id, impact) != command.preview_hash:
        raise PersonnelTransferConflict("the personnel transfer preview is stale")
    row = connection.execute(text(sql.INSPECT), vars(request)).mappings().one()
    valid = (
        int(str(row["source_version"])) == request.expected_membership_version
        and str(row["source_state"]) == "active"
        and row["source_valid_until"] is None
        and row["source_valid_from"] < request.effective_at
        and bool(row["target_active"])
        and int(str(row["target_version"])) == request.expected_target_unit_version
        and (
            not request.assignment_eligible
            or str(row["target_category"]) == OrganisationCategory.DELIVERY_TEAM.value
        )
    )
    if not valid:
        raise PersonnelTransferConflict("the transfer endpoints changed")
    if connection.execute(text(sql.OVERLAP), vars(request)).first() is not None:
        raise PersonnelTransferConflict("another membership overlaps the transfer destination")
    grant_ids = (
        request.source_authorising_grant_id,
        request.target_authorising_grant_id,
    )
    try:
        lock_lineages(connection, grant_ids)
        for at in {occurred_at, request.effective_at}:
            validate_lineage(
                connection,
                request.source_authorising_grant_id,
                command.actor_user_id,
                request.source_unit_id,
                ManagementAction.ROSTER_TRANSFER,
                at,
            )
            validate_lineage(
                connection,
                request.target_authorising_grant_id,
                command.actor_user_id,
                request.target_unit_id,
                ManagementAction.ROSTER_TRANSFER,
                at,
            )
    except OrganisationAuthorityDenied as error:
        raise PersonnelTransferDenied(
            "personnel transfer authority is no longer effective"
        ) from error


def _impact(connection: Connection, request: PersonnelTransferRequest) -> PersonnelTransferImpact:
    row = connection.execute(text(sql.INSPECT), vars(request)).mappings().first()
    if row is None:
        raise PersonnelTransferConflict("the transfer endpoints are unavailable")
    active_tasks = int(str(row["active_task_legs"]))
    state = {
        "membership_state": str(row["membership_state"]),
        "source_version": str(row["source_version"]),
        "target_version": str(row["target_version"]),
        "target_active": str(row["target_active"]),
        "active_task_legs": active_tasks,
    }
    digest = sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
    return PersonnelTransferImpact(active_tasks, 0, 0, 0, digest)


def _values(command: PersonnelTransferCommand, occurred_at: datetime) -> dict[str, object]:
    request = command.request
    return {
        **vars(request),
        "target_role": request.target_role.value,
        "command_id": command.command_id,
        "idempotency_key": command.idempotency_key,
        "actor_user_id": command.actor_user_id,
        "request_hash": command.preview_hash,
        "reason_hash": sha256(request.reason.encode()).hexdigest(),
        "occurred_at": occurred_at,
    }
