"""Persistence helpers for handover mutation and idempotent replay."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.work_package_handovers import (
    HandoverWorkPackageCommand,
    WorkPackageHandoverConflict,
    WorkPackageHandoverDenied,
    WorkPackageHandoverRequest,
    WorkPackageHandoverResult,
    handover_request_hash,
)
from coeus.persistence.organisation_authority_validation import transaction_time
from coeus.persistence.work_package_handover_sql import (
    ADD_TARGET,
    COMMANDS,
    END_SOURCE,
    END_TARGET_CONTRIBUTOR,
    PACKAGE,
    PACKAGE_FOR_UPDATE,
    RELEASE_RESERVATION,
)
from coeus.persistence.work_package_handover_validation import (
    validate_handover_grant,
    validate_target_ticket_authority,
)


def release_source_reservations(
    connection: Connection,
    request: WorkPackageHandoverRequest,
    reservations: tuple[RowMapping, ...],
    occurred_at: datetime,
) -> None:
    expected = {item.source_reservation_id: item for item in request.reservations}
    for row in reservations:
        changed = connection.execute(
            text(RELEASE_RESERVATION),
            {
                "reservation_id": row["reservation_id"],
                "expected_version": expected[row["reservation_id"]].expected_source_version,
                "at": occurred_at,
            },
        ).scalar_one_or_none()
        if changed is None:
            raise WorkPackageHandoverConflict("source reservation evidence changed")


def replace_participants(
    connection: Connection,
    request: WorkPackageHandoverRequest,
    source_user_id: UUID,
    occurred_at: datetime,
) -> None:
    values = {
        "package_id": request.package_id,
        "source_user_id": source_user_id,
        "target_user_id": request.target_user_id,
        "at": occurred_at,
    }
    connection.execute(text(END_SOURCE), values)
    connection.execute(text(END_TARGET_CONTRIBUTOR), values)
    connection.execute(text(ADD_TARGET), values)


def lock_handover_identities(connection: Connection, command: HandoverWorkPackageCommand) -> None:
    identities = sorted(
        (
            f"work-package-handover:command:{command.command_id}",
            f"work-package-handover:key:{command.actor_user_id}:{command.idempotency_key}",
        )
    )
    for identity in identities:
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:identity,0))"),
            {"identity": identity},
        )


def command_values(
    command: HandoverWorkPackageCommand,
    source_user_id: UUID,
    package_version: int,
    released: int,
    replacements: int,
    occurred_at: datetime,
) -> dict[str, object]:
    return {
        "command_id": command.command_id,
        "idempotency_key": command.idempotency_key,
        "request_hash": handover_request_hash(command.actor_user_id, command.request),
        "preview_hash": command.preview_hash,
        "package_id": command.request.package_id,
        "source_user_id": source_user_id,
        "target_user_id": command.request.target_user_id,
        "actor_user_id": command.actor_user_id,
        "expected_package_version": command.request.expected_package_version,
        "result_package_version": package_version,
        "released_count": released,
        "replacement_count": replacements,
        "occurred_at": occurred_at,
    }


def replay_handover(
    connection: Connection, command: HandoverWorkPackageCommand
) -> WorkPackageHandoverResult | None:
    rows = tuple(
        connection.execute(
            text(COMMANDS),
            {
                "command_id": command.command_id,
                "actor_user_id": command.actor_user_id,
                "idempotency_key": command.idempotency_key,
            },
        ).mappings()
    )
    if not rows:
        return None
    if len(rows) != 1:
        raise WorkPackageHandoverConflict("handover command identities conflict")
    row = rows[0]
    if (
        row["request_hash"] != handover_request_hash(command.actor_user_id, command.request)
        or row["preview_hash"] != command.preview_hash
        or row["actor_user_id"] != command.actor_user_id
        or row["package_id"] != command.request.package_id
        or row["target_user_id"] != command.request.target_user_id
    ):
        raise WorkPackageHandoverConflict("handover command identity was reused")
    package = (
        connection.execute(text(PACKAGE), {"package_id": command.request.package_id})
        .mappings()
        .first()
    )
    if (
        package is None
        or package["owning_unit_id"] != command.request.unit_id
        or package["ownership_unit_id"] != command.request.unit_id
        or package["ownership_state"] != "active"
        or package["accountable_user_id"] != command.request.target_user_id
    ):
        raise WorkPackageHandoverDenied("work package is unavailable")
    validate_target_ticket_authority(connection, command.request, package, lock=True)
    package = (
        connection.execute(text(PACKAGE_FOR_UPDATE), {"package_id": command.request.package_id})
        .mappings()
        .first()
    )
    if (
        package is None
        or package["owning_unit_id"] != command.request.unit_id
        or package["ownership_unit_id"] != command.request.unit_id
        or package["ownership_state"] != "active"
        or package["accountable_user_id"] != command.request.target_user_id
    ):
        raise WorkPackageHandoverDenied("work package is unavailable")
    validate_handover_grant(
        connection,
        command.actor_user_id,
        command.request,
        transaction_time(connection),
        package["owning_unit_id"],
    )
    return WorkPackageHandoverResult(
        row["package_id"],
        row["source_user_id"],
        row["target_user_id"],
        int(row["result_package_version"]),
        int(row["released_reservation_count"]),
        int(row["replacement_reservation_count"]),
        True,
    )
