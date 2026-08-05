"""Serializable, idempotent PostgreSQL personal-capacity reservations."""

import json
from datetime import datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.application.ports.capacity_reservations import CapacityReservationStore
from coeus.domain.capacity_forecast import forecast_capacity
from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.domain.work_packages import (
    CapacityAuthorityDenied,
    CapacityReservation,
    CapacityReservationConflict,
    CapacityReservationState,
    CapacityUnavailable,
    CapacityUnknown,
    ReserveCapacityCommand,
)
from coeus.persistence.capacity_reservation_evidence import (
    calendar_intervals as _calendar_intervals,
)
from coeus.persistence.capacity_reservation_evidence import (
    exception_minutes as _exception_minutes,
)
from coeus.persistence.capacity_reservation_evidence import (
    existing_reservation_minutes as _existing_reservation_minutes,
)
from coeus.persistence.capacity_reservation_evidence import (
    working_intervals as _working_intervals,
)
from coeus.persistence.capacity_reservation_evidence import (
    working_pattern as _working_pattern,
)
from coeus.persistence.capacity_reservation_sql import (
    AUTHORITY_PACKAGE as _AUTHORITY_PACKAGE,
)
from coeus.persistence.capacity_reservation_sql import (
    GRANTS as _GRANTS,
)
from coeus.persistence.capacity_reservation_sql import (
    INSERT as _INSERT,
)
from coeus.persistence.capacity_reservation_sql import (
    MEMBERSHIP as _MEMBERSHIP,
)
from coeus.persistence.capacity_reservation_sql import (
    PACKAGE as _PACKAGE,
)
from coeus.persistence.database_url import synchronous_database_url
from coeus.persistence.identity_account_projection import active_human_analyst_account
from coeus.persistence.organisation_authority_validation import transaction_time, validate_lineage
from coeus.persistence.serializable_retry import retry_serializable_once


class PostgresCapacityReservationStore(CapacityReservationStore):
    def __init__(self, database_url: str, *, policy_buffer_minutes: int = 0) -> None:
        if policy_buffer_minutes < 0 or policy_buffer_minutes % 15:
            raise ValueError("capacity policy buffer must use non-negative 15-minute increments")
        self._engine: Engine = create_engine(
            synchronous_database_url(database_url), pool_pre_ping=True
        )
        self._policy_buffer_minutes = policy_buffer_minutes

    def reserve(self, command: ReserveCapacityCommand) -> CapacityReservation:
        return retry_serializable_once(lambda: self._reserve_once(command))

    def _reserve_once(self, command: ReserveCapacityCommand) -> CapacityReservation:
        connection = self._engine.connect().execution_options(isolation_level="SERIALIZABLE")
        try:
            with connection.begin():
                return reserve_capacity_in_transaction(
                    connection, command, policy_buffer_minutes=self._policy_buffer_minutes
                )
        finally:
            connection.close()


def reserve_capacity_in_transaction(
    connection: Connection,
    command: ReserveCapacityCommand,
    *,
    policy_buffer_minutes: int = 0,
) -> CapacityReservation:
    """Reserve capacity within an existing atomic planning transaction."""
    request_hash = _request_hash(command)
    _lock_reservation_identities(connection, command)
    effective_at = transaction_time(connection)
    existing = _existing(connection, command)
    if existing is not None:
        _validate_owner_account(connection, command.user_id)
        if existing["request_hash"] != request_hash:
            raise CapacityReservationConflict(
                "capacity idempotency key was reused or reservation ID was reused"
            )
        package = _authority_package(connection, command.package_id)
        _validate_actor_authority(connection, command, package, effective_at)
        return reservation_from_row(existing)
    package = _lock_package(connection, command)
    _validate_owner_account(connection, command.user_id)
    _validate_actor_authority(connection, command, package, effective_at)
    _validate_current_membership(connection, command, package)
    pattern = _working_pattern(connection, command)
    working = _working_intervals(pattern, command.starts_at, command.ends_at)
    events = _calendar_intervals(connection, command)
    physical = forecast_capacity(working, events, (), 0, 0).physical_minutes
    deductions = _existing_reservation_minutes(connection, command)
    deductions += _exception_minutes(connection, command, physical)
    forecast = forecast_capacity(working, events, (), deductions, policy_buffer_minutes)
    if command.reserved_minutes > forecast.assignable_minutes:
        raise CapacityUnavailable("requested effort exceeds current assignable capacity")
    remaining = package["remaining_minutes"]
    if remaining is None:
        raise CapacityUnknown("work package needs a refined effort estimate")
    # ``remaining_minutes`` is the package's current net work estimate. Existing
    # reservations are calendar commitments, not completed work, so adding them
    # here would double-count effort on a re-plan.
    if command.reserved_minutes > int(remaining):
        raise CapacityUnavailable("reservation exceeds the package remaining effort")
    row = (
        connection.execute(
            text(_INSERT),
            {
                "reservation_id": command.reservation_id,
                "user_id": command.user_id,
                "ticket_id": command.ticket_id,
                "workflow_leg": command.workflow_leg.value,
                "package_id": command.package_id,
                "starts_at": command.starts_at,
                "ends_at": command.ends_at,
                "minutes": command.reserved_minutes,
                "key": command.idempotency_key,
                "request_hash": request_hash,
                "actor_id": command.actor_user_id,
                "now": effective_at,
                "participant_role": command.participant_role,
            },
        )
        .mappings()
        .one()
    )
    return reservation_from_row(row)


def _validate_owner_account(connection: Connection, user_id: UUID) -> None:
    if active_human_analyst_account(connection, user_id, lock=True) is None:
        raise CapacityAuthorityDenied("capacity owner account is not eligible")


def _existing(connection: Connection, command: ReserveCapacityCommand) -> RowMapping | None:
    rows = tuple(
        connection.execute(
            text(
                "SELECT * FROM capacity_reservations "
                "WHERE (actor_user_id=:actor_id AND idempotency_key=:key) "
                "OR reservation_id=:reservation_id "
                "ORDER BY reservation_id FOR UPDATE"
            ),
            {
                "actor_id": command.actor_user_id,
                "key": command.idempotency_key,
                "reservation_id": command.reservation_id,
            },
        ).mappings()
    )
    if len(rows) > 1:
        raise CapacityReservationConflict("capacity reservation identities conflict")
    return rows[0] if rows else None


def _lock_reservation_identities(connection: Connection, command: ReserveCapacityCommand) -> None:
    identities = sorted(
        (
            f"capacity-reservation:id:{command.reservation_id}",
            f"capacity-reservation:key:{command.actor_user_id}:{command.idempotency_key}",
            f"capacity-reservation:user:{command.user_id}",
        )
    )
    for identity in identities:
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:identity,0))"),
            {"identity": identity},
        )


def _lock_package(connection: Connection, command: ReserveCapacityCommand) -> RowMapping:
    row = (
        connection.execute(
            text(_PACKAGE),
            {"package_id": command.package_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise CapacityReservationConflict("work package is unavailable")
    if row["version"] != command.expected_package_version:
        raise CapacityReservationConflict("work package version changed")
    if row["ticket_id"] != command.ticket_id or row["workflow_leg"] != command.workflow_leg.value:
        raise CapacityReservationConflict("work package authority does not match the request")
    if command.participant_role == "accountable":
        participant_valid = row["accountable_user_id"] == command.user_id
    else:
        participant_valid = (
            connection.execute(
                text(
                    "SELECT 1 FROM work_package_participants WHERE package_id=:package_id "
                    "AND user_id=:user_id AND role='contributor' AND active FOR UPDATE"
                ),
                {"package_id": command.package_id, "user_id": command.user_id},
            ).scalar_one_or_none()
            is not None
        )
    if not participant_valid:
        raise CapacityReservationConflict("capacity owner is not an active package participant")
    return row


def _authority_package(connection: Connection, package_id: UUID) -> RowMapping:
    row = (
        connection.execute(text(_AUTHORITY_PACKAGE), {"package_id": package_id}).mappings().first()
    )
    if row is None:
        raise CapacityReservationConflict("work package authority is unavailable")
    return row


def _validate_current_membership(
    connection: Connection, command: ReserveCapacityCommand, package: RowMapping
) -> None:
    rows = tuple(
        connection.execute(
            text(_MEMBERSHIP),
            {"user_id": command.user_id, "start": command.starts_at, "end": command.ends_at},
        ).mappings()
    )
    if (
        len(rows) != 1
        or rows[0]["unit_id"] != package["owning_unit_id"]
        or not rows[0]["assignment_eligible"]
    ):
        raise CapacityUnknown("owner lacks one eligible home membership in the package team")


def _validate_actor_authority(
    connection: Connection,
    command: ReserveCapacityCommand,
    package: RowMapping,
    effective_at: datetime,
) -> None:
    grants = tuple(
        connection.execute(
            text(_GRANTS),
            {
                "actor_id": command.actor_user_id,
                "unit_id": package["owning_unit_id"],
                "at": effective_at,
            },
        ).mappings()
    )
    for grant in grants:
        try:
            validate_lineage(
                connection,
                grant["grant_id"],
                command.actor_user_id,
                grant["root_unit_id"],
                ManagementAction.TASK_ASSIGN,
                effective_at,
            )
            return
        except OrganisationAuthorityDenied:
            continue
    raise CapacityAuthorityDenied("current task assignment authority is required")


def _request_hash(command: ReserveCapacityCommand) -> str:
    payload = {
        "actor_user_id": str(command.actor_user_id),
        "ends_at": command.ends_at.isoformat(),
        "expected_package_version": command.expected_package_version,
        "package_id": str(command.package_id),
        "reservation_id": str(command.reservation_id),
        "reserved_minutes": command.reserved_minutes,
        "starts_at": command.starts_at.isoformat(),
        "ticket_id": str(command.ticket_id),
        "user_id": str(command.user_id),
        "workflow_leg": command.workflow_leg.value,
        "idempotency_key": command.idempotency_key,
        "participant_role": command.participant_role,
    }
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def reservation_from_row(row: RowMapping) -> CapacityReservation:
    return CapacityReservation(
        row["reservation_id"],
        row["user_id"],
        row["ticket_id"],
        WorkflowLeg(row["workflow_leg"]),
        row["package_id"],
        row["starts_at"],
        row["ends_at"],
        row["reserved_minutes"],
        CapacityReservationState(row["state"]),
        row["idempotency_key"],
        row["version"],
        row["created_at"],
        row["updated_at"],
        row["expires_at"],
    )
