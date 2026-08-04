"""Authorisation and atomic execution of workflow-leg transfer decisions."""

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.organisation import ManagementAction
from coeus.domain.tickets import TicketRecord
from coeus.domain.work_packages import (
    CapacityAuthorityDenied,
    CapacityReservationConflict,
    CapacityUnavailable,
    CapacityUnknown,
)
from coeus.domain.workflow_leg_transfers import (
    WorkflowLegTransferCommand,
    WorkflowLegTransferConflict,
    WorkflowLegTransferDenied,
    WorkflowLegTransferState,
)
from coeus.persistence.codec import decode_value
from coeus.persistence.workflow_leg_transfer_commands import UPDATE_OWNERSHIP, stored_proposal
from coeus.persistence.workflow_leg_transfer_execution import (
    apply_package_dispositions,
    update_ticket_assignment,
)
from coeus.persistence.workflow_leg_transfer_validation import (
    validate_grant,
    validate_proposal,
    validate_target,
)


def authorise_grants(
    connection: Connection,
    command: WorkflowLegTransferCommand,
    transfer: RowMapping,
    now: datetime,
) -> None:
    if command.grant_id is None or command.expected_grant_version is None:
        raise WorkflowLegTransferDenied("current task transfer authority is required")
    unit = (
        transfer["target_unit_id"]
        if command.action in {"accept", "reject"}
        else transfer["source_unit_id"]
    )
    validate_grant(
        connection,
        command.actor_user_id,
        command.grant_id,
        command.expected_grant_version,
        unit,
        now,
    )
    if command.action != "accept":
        return
    if command.assignment_grant_id is None or command.expected_assignment_grant_version is None:
        raise WorkflowLegTransferDenied("current task assignment authority is required")
    validate_grant(
        connection,
        command.actor_user_id,
        command.assignment_grant_id,
        command.expected_assignment_grant_version,
        transfer["target_unit_id"],
        now,
        ManagementAction.TASK_ASSIGN,
    )


def authorise_decision(
    connection: Connection,
    command: WorkflowLegTransferCommand,
    transfer: RowMapping,
    now: datetime,
) -> None:
    authorise_grants(connection, command, transfer, now)
    if command.action == "expire" and now < transfer["expires_at"]:
        raise WorkflowLegTransferConflict("workflow-leg transfer has not expired")


def apply_decision(
    connection: Connection,
    command: WorkflowLegTransferCommand,
    transfer: RowMapping,
    now: datetime,
    policy_buffer_minutes: int,
) -> tuple[WorkflowLegTransferState, int | None, int | None]:
    if now >= transfer["expires_at"]:
        return WorkflowLegTransferState.EXPIRED, None, None
    if command.action != "accept":
        state = {
            "cancel": WorkflowLegTransferState.CANCELLED,
            "reject": WorkflowLegTransferState.REJECTED,
            "expire": WorkflowLegTransferState.EXPIRED,
        }[command.action]
        return state, None, None
    if command.preview_hash != transfer["preview_hash"]:
        raise WorkflowLegTransferConflict("transfer preview is no longer current")
    required = (
        command.target_membership_id,
        command.expected_target_membership_version,
        command.expected_target_account_credential_version,
        command.expected_target_account_source_hash,
    )
    if any(item is None for item in required):
        raise WorkflowLegTransferDenied("target analyst evidence is required")
    proposal = stored_proposal(connection, transfer)
    _, ownership, packages = validate_proposal(
        connection, transfer["source_manager_user_id"], proposal, now, lock=True
    )
    starts = [item.starts_at for item in proposal.packages if item.starts_at is not None]
    ends = [item.ends_at for item in proposal.packages if item.ends_at is not None]
    assert command.target_membership_id is not None
    assert command.expected_target_membership_version is not None
    assert command.expected_target_account_credential_version is not None
    assert command.expected_target_account_source_hash is not None
    validate_target(
        connection,
        transfer["target_user_id"],
        transfer["target_unit_id"],
        command.target_membership_id,
        command.expected_target_membership_version,
        command.expected_target_account_credential_version,
        command.expected_target_account_source_hash,
        min(starts),
        max(ends),
    )
    ticket = _lock_ticket(connection, transfer)
    ticket_version = update_ticket_assignment(
        connection, ticket, transfer, command.actor_user_id, now
    )
    ownership_version = _update_ownership(connection, command, transfer, ownership, now)
    _apply_packages(connection, command, transfer, packages, now, policy_buffer_minutes)
    return WorkflowLegTransferState.ACCEPTED, ticket_version, ownership_version


def _lock_ticket(connection: Connection, transfer: RowMapping) -> TicketRecord:
    row = (
        connection.execute(
            text("SELECT payload FROM coeus_ticket_aggregates WHERE ticket_id=:id FOR UPDATE"),
            {"id": transfer["ticket_id"]},
        )
        .mappings()
        .one()
    )
    ticket = decode_value(dict(row["payload"]))
    if not isinstance(ticket, TicketRecord):
        raise WorkflowLegTransferDenied("workflow-leg transfer is unavailable")
    return ticket


def _update_ownership(
    connection: Connection,
    command: WorkflowLegTransferCommand,
    transfer: RowMapping,
    ownership: RowMapping,
    now: datetime,
) -> int:
    return int(
        connection.execute(
            text(UPDATE_OWNERSHIP),
            {
                "ticket_id": transfer["ticket_id"],
                "workflow_leg": transfer["workflow_leg"],
                "unit_id": transfer["target_unit_id"],
                "manager_id": command.actor_user_id,
                "history_reference": transfer["transfer_id"],
                "expected": ownership["version"],
                "at": now,
            },
        ).scalar_one()
    )


def _apply_packages(
    connection: Connection,
    command: WorkflowLegTransferCommand,
    transfer: RowMapping,
    packages: tuple[RowMapping, ...],
    now: datetime,
    policy_buffer_minutes: int,
) -> None:
    try:
        apply_package_dispositions(
            connection,
            transfer,
            packages,
            command.actor_user_id,
            now,
            policy_buffer_minutes,
        )
    except CapacityAuthorityDenied as exc:
        raise WorkflowLegTransferDenied("current task assignment authority is required") from exc
    except (CapacityReservationConflict, CapacityUnavailable, CapacityUnknown) as exc:
        raise WorkflowLegTransferConflict("target reservation could not be created") from exc
