"""Serializable package planning with an atomic capacity reservation."""

from hashlib import sha256
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.application.ports.work_package_planning import WorkPackagePlanningStore
from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.domain.work_package_planning import (
    PlanWorkPackageCommand,
    WorkPackagePlanningConflict,
    WorkPackagePlanningDenied,
    WorkPackagePlanningPreview,
    WorkPackagePlanningResult,
    WorkPackagePlanRequest,
    planning_hash,
)
from coeus.domain.work_packages import ReserveCapacityCommand
from coeus.persistence.capacity_reservations_postgres import (
    reservation_from_row,
    reserve_capacity_in_transaction,
)
from coeus.persistence.identity_account_projection import active_human_analyst_account
from coeus.persistence.organisation_authority_validation import transaction_time, validate_lineage
from coeus.persistence.serializable_retry import retry_serializable_once
from coeus.persistence.work_package_planning_evidence import (
    append_planning_evidence,
    planning_history_values,
)
from coeus.persistence.work_package_planning_sql import (
    COMMANDS,
    GRANT,
    INSERT_COMMAND,
    INSERT_HISTORY,
    MEMBERSHIP,
    PACKAGE,
    PACKAGE_FOR_UPDATE,
    UPDATE_PACKAGE,
)


class PostgresWorkPackagePlanningStore(WorkPackagePlanningStore):
    def __init__(self, engine: Engine, *, policy_buffer_minutes: int = 0) -> None:
        self._engine = engine
        self._policy_buffer_minutes = policy_buffer_minutes

    def preview(
        self, actor_user_id: UUID, request: WorkPackagePlanRequest
    ) -> WorkPackagePlanningPreview:
        connection = self._engine.connect().execution_options(isolation_level="SERIALIZABLE")
        try:
            with connection.begin():
                row, account = _load_and_validate(connection, actor_user_id, request, lock=True)
                return _preview(actor_user_id, request, row, account)
        finally:
            connection.close()

    def execute(self, command: PlanWorkPackageCommand) -> WorkPackagePlanningResult:
        return retry_serializable_once(lambda: self._execute_once(command))

    def _execute_once(self, command: PlanWorkPackageCommand) -> WorkPackagePlanningResult:
        connection = self._engine.connect().execution_options(isolation_level="SERIALIZABLE")
        try:
            with connection.begin():
                replay = _replay(connection, command)
                if replay is not None:
                    return replay
                row, account = _load_and_validate(
                    connection, command.actor_user_id, command.request, lock=True
                )
                preview = _preview(command.actor_user_id, command.request, row, account)
                if preview.preview_hash != command.preview_hash:
                    raise WorkPackagePlanningConflict("planning preview is no longer current")
                return self._apply(connection, command, row)
        finally:
            connection.close()

    def _apply(
        self, connection: Connection, command: PlanWorkPackageCommand, row: RowMapping
    ) -> WorkPackagePlanningResult:
        occurred_at = transaction_time(connection)
        package_version = int(
            connection.execute(
                text(UPDATE_PACKAGE),
                {
                    "package_id": command.request.package_id,
                    "expected_version": command.request.expected_package_version,
                    "estimated_minutes": command.request.estimated_minutes,
                    "remaining_minutes": command.request.remaining_minutes,
                    "due_at": command.request.due_at,
                    "priority": command.request.priority,
                    "priority_override_reason": (command.request.priority_override_reason.strip()),
                    "now": occurred_at,
                },
            ).scalar_one()
        )
        reservation = reserve_capacity_in_transaction(
            connection,
            ReserveCapacityCommand(
                command.request.reservation_id,
                command.actor_user_id,
                command.request.accountable_user_id,
                row["ticket_id"],
                WorkflowLeg(row["workflow_leg"]),
                command.request.package_id,
                command.request.starts_at,
                command.request.ends_at,
                command.request.reserved_minutes,
                command.idempotency_key,
                package_version,
            ),
            policy_buffer_minutes=self._policy_buffer_minutes,
        )
        request_hash = planning_hash(command.actor_user_id, command.request)
        connection.execute(
            text(INSERT_HISTORY),
            planning_history_values(command, package_version, occurred_at),
        )
        connection.execute(
            text(INSERT_COMMAND),
            {
                "command_id": command.command_id,
                "idempotency_key": command.idempotency_key,
                "request_hash": request_hash,
                "package_id": command.request.package_id,
                "actor_user_id": command.actor_user_id,
                "expected_version": command.request.expected_package_version,
                "result_version": package_version,
                "occurred_at": occurred_at,
            },
        )
        append_planning_evidence(connection, command, package_version, occurred_at)
        return WorkPackagePlanningResult(
            command.request.package_id, package_version, reservation, False
        )


def _preview(
    actor_user_id: UUID,
    request: WorkPackagePlanRequest,
    row: RowMapping,
    account: RowMapping,
) -> WorkPackagePlanningPreview:
    evidence = (
        f"{planning_hash(actor_user_id, request)}:"
        f"{account['credential_version']}:{account['source_hash']}"
    )
    return WorkPackagePlanningPreview(
        sha256(evidence.encode()).hexdigest(),
        request.package_id,
        int(row["version"]),
        int(row["ownership_version"]),
        row["accountable_user_id"],
        int(row["version"]) + 1,
    )


def _load_and_validate(
    connection: Connection,
    actor_user_id: UUID,
    request: WorkPackagePlanRequest,
    *,
    lock: bool,
) -> tuple[RowMapping, RowMapping]:
    row = (
        connection.execute(
            text(PACKAGE_FOR_UPDATE if lock else PACKAGE),
            {"package_id": request.package_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise WorkPackagePlanningDenied("work package is unavailable")
    if (
        row["version"] != request.expected_package_version
        or row["ownership_version"] != request.expected_ownership_version
    ):
        raise WorkPackagePlanningConflict("work package planning evidence changed")
    account = _validate_current_scope(connection, actor_user_id, request, row)
    return row, account


def _validate_current_scope(
    connection: Connection,
    actor_user_id: UUID,
    request: WorkPackagePlanRequest,
    row: RowMapping,
) -> RowMapping:
    if (
        row["owning_unit_id"] != request.unit_id
        or row["ownership_unit_id"] != request.unit_id
        or row["ownership_state"] != "active"
        or row["accountable_user_id"] != request.accountable_user_id
        or row["state"] not in {"pending", "ready", "in_progress"}
    ):
        raise WorkPackagePlanningDenied("work package is outside current planning authority")
    occurred_at = transaction_time(connection)
    account = active_human_analyst_account(connection, request.accountable_user_id, lock=True)
    if account is None or account["user_id"] != row["accountable_user_id"]:
        raise WorkPackagePlanningDenied("accountable owner account is not eligible")
    grant = (
        connection.execute(
            text(GRANT),
            {
                "grant_id": request.authorising_grant_id,
                "actor_id": actor_user_id,
                "unit_id": request.unit_id,
                "at": occurred_at,
            },
        )
        .mappings()
        .first()
    )
    if grant is None:
        raise WorkPackagePlanningDenied("current task assignment authority is required")
    try:
        validate_lineage(
            connection,
            grant["grant_id"],
            actor_user_id,
            grant["root_unit_id"],
            ManagementAction.TASK_ASSIGN,
            occurred_at,
        )
    except OrganisationAuthorityDenied as exc:
        raise WorkPackagePlanningDenied("current task assignment authority is required") from exc
    memberships = tuple(
        connection.execute(
            text(MEMBERSHIP),
            {
                "user_id": request.accountable_user_id,
                "unit_id": request.unit_id,
                "starts_at": request.starts_at,
                "ends_at": request.ends_at,
            },
        ).mappings()
    )
    if len(memberships) != 1:
        raise WorkPackagePlanningDenied("accountable owner is not eligible for the full interval")
    return account


def _replay(
    connection: Connection, command: PlanWorkPackageCommand
) -> WorkPackagePlanningResult | None:
    rows = tuple(
        connection.execute(
            text(COMMANDS),
            {
                "command_id": command.command_id,
                "idempotency_key": command.idempotency_key,
            },
        ).mappings()
    )
    if not rows:
        return None
    expected_hash = planning_hash(command.actor_user_id, command.request)
    if len(rows) != 1:
        raise WorkPackagePlanningConflict("planning command identities conflict")
    row = rows[0]
    if (
        row["request_hash"] != expected_hash
        or row["actor_user_id"] != command.actor_user_id
        or row["package_id"] != command.request.package_id
        or row["operation"] != "update"
    ):
        raise WorkPackagePlanningConflict("planning command identity was reused")
    current = (
        connection.execute(text(PACKAGE_FOR_UPDATE), {"package_id": command.request.package_id})
        .mappings()
        .first()
    )
    if current is None:
        raise WorkPackagePlanningDenied("work package is unavailable")
    _validate_current_scope(connection, command.actor_user_id, command.request, current)
    reservation_row = (
        connection.execute(
            text("SELECT * FROM capacity_reservations WHERE reservation_id=:reservation_id"),
            {"reservation_id": command.request.reservation_id},
        )
        .mappings()
        .first()
    )
    if reservation_row is None:
        raise WorkPackagePlanningConflict("planning reservation evidence is unavailable")
    return WorkPackagePlanningResult(
        command.request.package_id,
        int(row["result_version"]),
        reservation_from_row(reservation_row),
        True,
    )
