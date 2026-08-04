"""Command identity, replay and proposal reconstruction helpers."""

# ruff: noqa: E501

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.domain.workflow_leg_transfers import (
    PackageTransferDisposition,
    PackageTransferPlan,
    ProposeWorkflowLegTransfer,
    WorkflowLegTransferConflict,
    WorkflowLegTransferDenied,
    WorkflowLegTransferResult,
    WorkflowLegTransferState,
    proposal_hash,
)

INSERT_TRANSFER = """INSERT INTO workflow_leg_transfers(transfer_id,ticket_id,workflow_leg,
source_unit_id,target_unit_id,target_user_id,source_manager_user_id,state,expected_ownership_version,
expected_ticket_version,expected_ticket_source_hash,source_grant_id,source_grant_version,proposal_hash,
preview_hash,expires_at,reason,version,created_at,updated_at) VALUES(:transfer_id,:ticket_id,:workflow_leg,
:source_unit_id,:target_unit_id,:target_user_id,:source_manager,'proposed',:expected_ownership_version,
:expected_ticket_version,:expected_ticket_source_hash,:authorising_grant_id,:expected_grant_version,
:proposal_hash,:preview_hash,:expires_at,:reason,1,:at,:at)"""
INSERT_PACKAGE = """INSERT INTO workflow_leg_transfer_packages VALUES(:transfer_id,:package_id,
:disposition,:expected_version,:reservation_id,:reservation_idempotency_key,:starts_at,:ends_at,:reserved_minutes)"""
TRANSFER_FOR_UPDATE = (
    "SELECT * FROM workflow_leg_transfers WHERE transfer_id=:transfer_id FOR UPDATE"
)
UPDATE_TRANSFER = """UPDATE workflow_leg_transfers SET state=:state,target_manager_user_id=:target_manager,
result_ticket_version=:ticket_version,result_ownership_version=:ownership_version,decision_reason=:reason,
version=:version,updated_at=:at,decided_at=:at WHERE transfer_id=:transfer_id"""
UPDATE_OWNERSHIP = """UPDATE team_task_ownership SET owning_unit_id=:unit_id,
manager_user_id=:manager_id,version=version+1,history_reference=:history_reference,updated_at=:at
WHERE ticket_id=:ticket_id AND workflow_leg=:workflow_leg AND version=:expected RETURNING version"""


def stored_proposal(connection: Connection, transfer: RowMapping) -> ProposeWorkflowLegTransfer:
    rows = connection.execute(
        text("""SELECT * FROM workflow_leg_transfer_packages
WHERE transfer_id=:id ORDER BY package_id FOR UPDATE"""),
        {"id": transfer["transfer_id"]},
    )
    packages = tuple(
        PackageTransferPlan(
            row["package_id"],
            PackageTransferDisposition(row["disposition"]),
            int(row["expected_version"]),
            row["reservation_id"],
            row["reservation_idempotency_key"],
            row["starts_at"],
            row["ends_at"],
            row["reserved_minutes"],
        )
        for row in rows.mappings()
    )
    return ProposeWorkflowLegTransfer(
        transfer["transfer_id"],
        transfer["ticket_id"],
        WorkflowLeg(transfer["workflow_leg"]),
        transfer["source_unit_id"],
        transfer["target_unit_id"],
        transfer["target_user_id"],
        int(transfer["expected_ownership_version"]),
        int(transfer["expected_ticket_version"]),
        transfer["expected_ticket_source_hash"],
        transfer["source_grant_id"],
        int(transfer["source_grant_version"]),
        transfer["expires_at"],
        packages,
        transfer["reason"],
    )


def lock_commands(connection: Connection, command_id: UUID, actor: UUID, key: str) -> None:
    for identity in sorted(
        (f"workflow-transfer:command:{command_id}", f"workflow-transfer:key:{actor}:{key}")
    ):
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:id,0))"), {"id": identity}
        )


def replay(
    connection: Connection, command_id: UUID, actor: UUID, key: str, request_hash: str
) -> WorkflowLegTransferResult | None:
    rows = tuple(
        connection.execute(
            text("""SELECT * FROM workflow_leg_transfer_commands
WHERE command_id=:command_id OR(actor_user_id=:actor AND idempotency_key=:key) FOR UPDATE"""),
            {"command_id": command_id, "actor": actor, "key": key},
        ).mappings()
    )
    if not rows:
        return None
    if len(rows) != 1:
        raise WorkflowLegTransferConflict("transfer command identity was reused")
    if rows[0]["actor_user_id"] != actor:
        raise WorkflowLegTransferDenied("workflow-leg transfer is unavailable")
    if rows[0]["request_hash"] != request_hash:
        raise WorkflowLegTransferConflict("transfer command identity was reused")
    row = rows[0]
    return WorkflowLegTransferResult(
        row["transfer_id"],
        WorkflowLegTransferState(row["result_state"]),
        int(row["result_version"]),
        True,
    )


def insert_command(
    connection: Connection,
    command_id: UUID,
    actor: UUID,
    key: str,
    transfer_id: UUID,
    action: str,
    request_hash: str,
    state: WorkflowLegTransferState,
    version: int,
    at: datetime,
) -> None:
    connection.execute(
        text("""INSERT INTO workflow_leg_transfer_commands
(command_id,actor_user_id,idempotency_key,transfer_id,action,request_hash,result_state,result_version,occurred_at)
VALUES(:command_id,:actor,:key,:transfer_id,:action,:hash,:state,:version,:at)"""),
        {
            "command_id": command_id,
            "actor": actor,
            "key": key,
            "transfer_id": transfer_id,
            "action": action,
            "hash": request_hash,
            "state": state.value,
            "version": version,
            "at": at,
        },
    )


def transfer_values(
    actor: UUID, proposal: ProposeWorkflowLegTransfer, digest: str, at: datetime
) -> dict[str, object]:
    return {
        **vars(proposal),
        "workflow_leg": proposal.workflow_leg.value,
        "source_manager": actor,
        "proposal_hash": proposal_hash(actor, proposal),
        "preview_hash": digest,
        "at": at,
    }


def package_values(transfer_id: UUID, plan: PackageTransferPlan) -> dict[str, object]:
    return {"transfer_id": transfer_id, **vars(plan), "disposition": plan.disposition.value}


def lock_new_transfer(connection: Connection, transfer_id: UUID) -> None:
    connection.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:id,0))"),
        {"id": f"workflow-transfer:aggregate:{transfer_id}"},
    )
    existing = connection.execute(
        text("SELECT 1 FROM workflow_leg_transfers WHERE transfer_id=:id"),
        {"id": transfer_id},
    ).scalar_one_or_none()
    if existing is not None:
        raise WorkflowLegTransferConflict("transfer identity was reused")
