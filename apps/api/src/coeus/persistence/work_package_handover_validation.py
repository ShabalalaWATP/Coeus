"""Validation and inventory binding for accountable-owner handover."""

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.enums import TicketState
from coeus.domain.jioc_principals import PrincipalKind, principal_kind
from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.team_task_ownership import WorkflowLeg, delivery_route_for_leg
from coeus.domain.tickets import TicketRecord
from coeus.domain.work_package_handovers import (
    WorkPackageHandoverConflict,
    WorkPackageHandoverDenied,
    WorkPackageHandoverPreview,
    WorkPackageHandoverRequest,
    handover_preview_hash,
    handover_request_hash,
)
from coeus.persistence.codec import decode_value
from coeus.persistence.identity_account_projection import active_analyst_role
from coeus.persistence.organisation_authority_validation import transaction_time, validate_lineage
from coeus.persistence.work_package_handover_sql import (
    ACCOUNT,
    DEPENDENCIES,
    GRANT,
    MEMBERSHIP,
    PACKAGE,
    PACKAGE_FOR_UPDATE,
    PARTICIPANTS,
    RESERVATIONS,
    TICKET_AUTHORITY,
    TICKET_AUTHORITY_FOR_UPDATE,
)

_ACTIVE_STATES = {"pending", "ready", "in_progress", "blocked"}


def load_and_validate_handover(
    connection: Connection,
    actor_user_id: UUID,
    request: WorkPackageHandoverRequest,
    *,
    lock: bool,
) -> dict[str, object]:
    package = (
        connection.execute(text(PACKAGE), {"package_id": request.package_id}).mappings().first()
    )
    if package is None:
        raise WorkPackageHandoverDenied("work package is unavailable")
    _validate_package_scope(request, package)
    ticket_authority = validate_target_ticket_authority(connection, request, package, lock=lock)
    if lock:
        locked_package = (
            connection.execute(text(PACKAGE_FOR_UPDATE), {"package_id": request.package_id})
            .mappings()
            .first()
        )
        if (
            locked_package is None
            or locked_package["ticket_id"] != package["ticket_id"]
            or locked_package["workflow_leg"] != package["workflow_leg"]
        ):
            raise WorkPackageHandoverDenied("work package is unavailable")
        package = locked_package
        _validate_package_scope(request, package)
    occurred_at = transaction_time(connection)
    validate_handover_grant(
        connection, actor_user_id, request, occurred_at, package["owning_unit_id"]
    )
    _validate_package(request, package)
    participants = tuple(
        connection.execute(text(PARTICIPANTS), {"package_id": request.package_id}).mappings()
    )
    reservations = tuple(
        connection.execute(text(RESERVATIONS), {"package_id": request.package_id}).mappings()
    )
    dependencies = tuple(
        connection.execute(text(DEPENDENCIES), {"package_id": request.package_id}).mappings()
    )
    _validate_participants(package, request, participants)
    source_reservations = _validate_reservations(package, request, reservations)
    _validate_target(connection, request, source_reservations, occurred_at)
    return {
        "package": package,
        "participants": participants,
        "reservations": reservations,
        "source_reservations": source_reservations,
        "dependencies": dependencies,
        "ticket_authority": ticket_authority,
    }


def _validate_package_scope(request: WorkPackageHandoverRequest, package: RowMapping) -> None:
    if (
        package["owning_unit_id"] != request.unit_id
        or package["ownership_unit_id"] != request.unit_id
    ):
        raise WorkPackageHandoverDenied("work package is unavailable")


def _validate_package(request: WorkPackageHandoverRequest, package: RowMapping) -> None:
    if (
        int(package["version"]) != request.expected_package_version
        or int(package["ownership_version"]) != request.expected_ownership_version
    ):
        raise WorkPackageHandoverConflict("work-package evidence changed")
    if (
        package["ownership_state"] != "active"
        or package["state"] not in _ACTIVE_STATES
        or package["accountable_user_id"] is None
    ):
        raise WorkPackageHandoverDenied("work package is unavailable")
    if package["accountable_user_id"] == request.target_user_id:
        raise WorkPackageHandoverConflict("target is already the accountable owner")


def validate_handover_grant(
    connection: Connection,
    actor_user_id: UUID,
    request: WorkPackageHandoverRequest,
    occurred_at: datetime,
    unit_id: UUID,
) -> None:
    grant = (
        connection.execute(
            text(GRANT),
            {
                "grant_id": request.authorising_grant_id,
                "actor_id": actor_user_id,
                "unit_id": unit_id,
                "at": occurred_at,
            },
        )
        .mappings()
        .first()
    )
    if grant is None or int(grant["version"]) != request.expected_grant_version:
        raise WorkPackageHandoverDenied("current task assignment authority is required")
    try:
        validate_lineage(
            connection,
            grant["grant_id"],
            actor_user_id,
            unit_id,
            ManagementAction.TASK_ASSIGN,
            occurred_at,
        )
    except OrganisationAuthorityDenied as exc:
        raise WorkPackageHandoverDenied("current task assignment authority is required") from exc


def _validate_participants(
    package: RowMapping,
    request: WorkPackageHandoverRequest,
    participants: tuple[RowMapping, ...],
) -> None:
    accountable = [row for row in participants if row["role"] == "accountable" and row["active"]]
    if len(accountable) != 1 or accountable[0]["user_id"] != package["accountable_user_id"]:
        raise WorkPackageHandoverConflict("accountable participant evidence is inconsistent")
    if any(
        row["user_id"] == request.target_user_id and row["role"] == "accountable" and row["active"]
        for row in participants
    ):
        raise WorkPackageHandoverConflict("target participant evidence is inconsistent")


def _validate_reservations(
    package: RowMapping,
    request: WorkPackageHandoverRequest,
    reservations: tuple[RowMapping, ...],
) -> tuple[RowMapping, ...]:
    if len(reservations) > 64:
        raise WorkPackageHandoverDenied("reservation inventory exceeds the review boundary")
    expected = {item.source_reservation_id: item for item in request.reservations}
    source = tuple(row for row in reservations if row["user_id"] == package["accountable_user_id"])
    actual = {row["reservation_id"]: row for row in source}
    if set(expected) != set(actual):
        raise WorkPackageHandoverConflict("every live reservation needs a disposition")
    for reservation_id, row in actual.items():
        item = expected[reservation_id]
        if int(row["version"]) != item.expected_source_version:
            raise WorkPackageHandoverConflict("source reservation evidence changed")
    return source


def validate_target_ticket_authority(
    connection: Connection,
    request: WorkPackageHandoverRequest,
    package: RowMapping,
    *,
    lock: bool,
) -> RowMapping:
    row = (
        connection.execute(
            text(TICKET_AUTHORITY_FOR_UPDATE if lock else TICKET_AUTHORITY),
            {"ticket_id": package["ticket_id"]},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise WorkPackageHandoverDenied("work package is unavailable")
    payload = row["payload"]
    ticket = decode_value(dict(payload)) if isinstance(payload, dict) else None
    route = delivery_route_for_leg(WorkflowLeg(str(package["workflow_leg"])))
    assignments = (
        tuple(
            assignment
            for assignment in ticket.analyst_assignments
            if assignment.active
            and assignment.analyst_user_id == request.target_user_id
            and assignment.route.value == route
            and assignment.team_id == request.unit_id
        )
        if isinstance(ticket, TicketRecord)
        and ticket.state in {TicketState.ANALYST_IN_PROGRESS, TicketState.REWORK_REQUIRED}
        else ()
    )
    if (
        int(row["version"]) != request.expected_ticket_version
        or str(row["canonical_hash"]) != request.expected_ticket_source_hash
        or len(assignments) != 1
    ):
        raise WorkPackageHandoverDenied("work package is unavailable")
    return row


def _validate_target(
    connection: Connection,
    request: WorkPackageHandoverRequest,
    reservations: tuple[RowMapping, ...],
    occurred_at: datetime,
) -> None:
    if principal_kind(request.target_user_id) is not PrincipalKind.HUMAN:
        raise WorkPackageHandoverDenied("target must be a human analyst")
    account = (
        connection.execute(text(ACCOUNT), {"user_id": request.target_user_id}).mappings().first()
    )
    if (
        account is None
        or not account["is_active"]
        or active_analyst_role() not in account["roles"]
        or int(account["credential_version"]) != request.expected_target_account_credential_version
        or str(account["source_hash"]) != request.expected_target_account_source_hash
    ):
        raise WorkPackageHandoverDenied("target account evidence is not eligible")
    starts_at = min((row["starts_at"] for row in reservations), default=occurred_at)
    ends_at = max((row["ends_at"] for row in reservations), default=occurred_at)
    memberships = tuple(
        connection.execute(
            text(MEMBERSHIP),
            {"user_id": request.target_user_id, "start": starts_at, "end": ends_at},
        ).mappings()
    )
    if len(memberships) != 1:
        raise WorkPackageHandoverDenied("target needs one eligible posting for the handover")
    membership = memberships[0]
    if (
        membership["membership_id"] != request.target_membership_id
        or membership["unit_id"] != request.unit_id
        or int(membership["version"]) != request.expected_target_membership_version
    ):
        raise WorkPackageHandoverDenied("target home-posting evidence changed")


def preview_handover(
    actor_user_id: UUID,
    request: WorkPackageHandoverRequest,
    evidence: dict[str, object],
) -> WorkPackageHandoverPreview:
    # The evidence map is built by this module's own collector, so its shape is
    # fixed here rather than re-checked on every read.
    package = cast(RowMapping, evidence["package"])
    participants = cast(tuple[RowMapping, ...], evidence["participants"])
    reservations = cast(tuple[RowMapping, ...], evidence["reservations"])
    dependencies = cast(tuple[RowMapping, ...], evidence["dependencies"])
    ticket_authority = cast(RowMapping, evidence["ticket_authority"])
    inventory = {
        "dependencies": [
            [str(row["package_id"]), str(row["predecessor_package_id"])] for row in dependencies
        ],
        "ownership_version": int(package["ownership_version"]),
        "package_version": int(package["version"]),
        "participants": [
            [str(row["user_id"]), row["role"], bool(row["active"])] for row in participants
        ],
        "ticket_authority": [
            int(ticket_authority["version"]),
            str(ticket_authority["canonical_hash"]),
        ],
        "reservations": [
            [str(row["reservation_id"]), str(row["user_id"]), row["state"], int(row["version"])]
            for row in reservations
        ],
    }
    return WorkPackageHandoverPreview(
        handover_preview_hash(handover_request_hash(actor_user_id, request), inventory),
        request.package_id,
        package["accountable_user_id"],
        request.target_user_id,
        int(package["version"]),
        int(package["version"]) + 1,
        len(participants),
        len(reservations),
        len(dependencies),
    )
