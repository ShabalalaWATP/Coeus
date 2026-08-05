"""Serializable accountable-owner handover with reservation reconciliation."""

from typing import cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.application.ports.work_package_handovers import WorkPackageHandoverStore
from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.domain.work_package_handovers import (
    HandoverWorkPackageCommand,
    ReservationDisposition,
    WorkPackageHandoverConflict,
    WorkPackageHandoverDenied,
    WorkPackageHandoverPreview,
    WorkPackageHandoverRequest,
    WorkPackageHandoverResult,
)
from coeus.domain.work_packages import (
    CapacityAuthorityDenied,
    CapacityReservationConflict,
    CapacityUnavailable,
    CapacityUnknown,
    ReserveCapacityCommand,
)
from coeus.persistence.capacity_reservations_postgres import reserve_capacity_in_transaction
from coeus.persistence.organisation_authority_validation import transaction_time
from coeus.persistence.serializable_retry import retry_serializable_once
from coeus.persistence.work_package_handover_evidence import (
    append_handover_evidence,
    handover_history_values,
)
from coeus.persistence.work_package_handover_execution import (
    command_values,
    lock_handover_identities,
    release_source_reservations,
    replace_participants,
    replay_handover,
)
from coeus.persistence.work_package_handover_sql import (
    INSERT_COMMAND,
    INSERT_HISTORY,
    UPDATE_PACKAGE,
)
from coeus.persistence.work_package_handover_validation import (
    load_and_validate_handover,
    preview_handover,
)


class PostgresWorkPackageHandoverStore(WorkPackageHandoverStore):
    def __init__(self, engine: Engine, *, policy_buffer_minutes: int = 0) -> None:
        self._engine = engine
        self._policy_buffer_minutes = policy_buffer_minutes

    def preview(
        self, actor_user_id: UUID, request: WorkPackageHandoverRequest
    ) -> WorkPackageHandoverPreview:
        with self._engine.begin() as connection:
            evidence = load_and_validate_handover(connection, actor_user_id, request, lock=False)
            return preview_handover(actor_user_id, request, evidence)

    def execute(self, command: HandoverWorkPackageCommand) -> WorkPackageHandoverResult:
        return retry_serializable_once(lambda: self._execute_once(command))

    def _execute_once(self, command: HandoverWorkPackageCommand) -> WorkPackageHandoverResult:
        connection = self._engine.connect().execution_options(isolation_level="SERIALIZABLE")
        try:
            with connection.begin():
                lock_handover_identities(connection, command)
                replay = replay_handover(connection, command)
                if replay is not None:
                    return replay
                evidence = load_and_validate_handover(
                    connection, command.actor_user_id, command.request, lock=True
                )
                preview = preview_handover(command.actor_user_id, command.request, evidence)
                if preview.preview_hash != command.preview_hash:
                    raise WorkPackageHandoverConflict("handover preview is no longer current")
                return self._apply(connection, command, evidence)
        finally:
            connection.close()

    def _apply(
        self,
        connection: Connection,
        command: HandoverWorkPackageCommand,
        evidence: dict[str, object],
    ) -> WorkPackageHandoverResult:
        request = command.request
        # The evidence map is assembled by the validation module, so its shape is
        # fixed here rather than re-checked on every read.
        package = cast(RowMapping, evidence["package"])
        reservations = cast(tuple[RowMapping, ...], evidence["source_reservations"])
        source_user_id = package["accountable_user_id"]
        occurred_at = transaction_time(connection)
        for user_id in sorted((source_user_id, request.target_user_id), key=str):
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:user_id,0))"),
                {"user_id": str(user_id)},
            )
        release_source_reservations(connection, request, reservations, occurred_at)
        package_version = int(
            connection.execute(
                text(UPDATE_PACKAGE),
                {
                    "package_id": request.package_id,
                    "target_user_id": request.target_user_id,
                    "expected_version": request.expected_package_version,
                    "at": occurred_at,
                },
            ).scalar_one()
        )
        replace_participants(connection, request, source_user_id, occurred_at)
        replacements = self._create_replacements(
            connection, command, package, reservations, package_version
        )
        connection.execute(
            text(INSERT_HISTORY),
            handover_history_values(command, source_user_id, package_version, occurred_at),
        )
        connection.execute(
            text(INSERT_COMMAND),
            command_values(
                command,
                source_user_id,
                package_version,
                len(reservations),
                replacements,
                occurred_at,
            ),
        )
        append_handover_evidence(connection, command, source_user_id, package_version, occurred_at)
        return WorkPackageHandoverResult(
            request.package_id,
            source_user_id,
            request.target_user_id,
            package_version,
            len(reservations),
            replacements,
            False,
        )

    def _create_replacements(
        self,
        connection: Connection,
        command: HandoverWorkPackageCommand,
        package: RowMapping,
        reservations: tuple[RowMapping, ...],
        package_version: int,
    ) -> int:
        by_id = {row["reservation_id"]: row for row in reservations}
        count = 0
        try:
            for item in command.request.reservations:
                if item.disposition is ReservationDisposition.RELEASE:
                    continue
                source = by_id[item.source_reservation_id]
                # Anything other than a release carries both halves of its
                # replacement evidence, which the request schema enforces.
                reserve_capacity_in_transaction(
                    connection,
                    ReserveCapacityCommand(
                        cast(UUID, item.replacement_reservation_id),
                        command.actor_user_id,
                        command.request.target_user_id,
                        package["ticket_id"],
                        WorkflowLeg(package["workflow_leg"]),
                        command.request.package_id,
                        source["starts_at"],
                        source["ends_at"],
                        int(source["reserved_minutes"]),
                        cast(str, item.replacement_idempotency_key),
                        package_version,
                    ),
                    policy_buffer_minutes=self._policy_buffer_minutes,
                )
                count += 1
        except CapacityAuthorityDenied as exc:
            raise WorkPackageHandoverDenied(
                "current task assignment authority is required"
            ) from exc
        except (CapacityReservationConflict, CapacityUnavailable, CapacityUnknown) as exc:
            raise WorkPackageHandoverConflict("target reservation could not be created") from exc
        return count
