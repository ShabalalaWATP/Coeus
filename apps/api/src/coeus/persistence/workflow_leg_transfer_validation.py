"""Privacy-preserving validation for cross-team workflow-leg transfer."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.enums import TicketState
from coeus.domain.jioc_principals import PrincipalKind, principal_kind
from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.team_task_ownership import delivery_route_for_leg
from coeus.domain.tickets import TicketRecord
from coeus.domain.workflow_leg_transfers import (
    PackageTransferDisposition,
    ProposeWorkflowLegTransfer,
    WorkflowLegTransferConflict,
    WorkflowLegTransferDenied,
    WorkflowLegTransferPreview,
    preview_hash,
)
from coeus.persistence.codec import decode_value
from coeus.persistence.identity_account_projection import active_analyst_role
from coeus.persistence.organisation_authority_validation import validate_lineage

_OWNERSHIP = """SELECT * FROM team_task_ownership WHERE ticket_id=:ticket_id
AND workflow_leg=:workflow_leg"""
_PACKAGES = """SELECT * FROM canonical_work_packages WHERE ticket_id=:ticket_id
AND workflow_leg=:workflow_leg ORDER BY package_id"""
_TICKET = (
    "SELECT version,canonical_hash,payload FROM coeus_ticket_aggregates WHERE ticket_id=:ticket_id"
)
_DEPENDENCIES = """SELECT package_id,predecessor_package_id FROM work_package_dependencies
WHERE package_id=ANY(:package_ids) OR predecessor_package_id=ANY(:package_ids)
ORDER BY package_id,predecessor_package_id"""
_GRANT = """SELECT * FROM team_management_grants WHERE grant_id=:grant_id
AND manager_user_id=:actor_id AND valid_from<=:at
AND(valid_until IS NULL OR :at<valid_until) AND(revoked_at IS NULL OR :at<revoked_at) FOR UPDATE"""


def validate_proposal(
    connection: Connection,
    actor_user_id: UUID,
    proposal: ProposeWorkflowLegTransfer,
    now: datetime,
    *,
    lock: bool,
) -> tuple[WorkflowLegTransferPreview, RowMapping, tuple[RowMapping, ...]]:
    ownership_values = {
        "ticket_id": proposal.ticket_id,
        "workflow_leg": proposal.workflow_leg.value,
    }
    ownership = connection.execute(text(_OWNERSHIP), ownership_values).mappings().first()
    if ownership is None or ownership["owning_unit_id"] != proposal.source_unit_id:
        raise WorkflowLegTransferDenied("workflow-leg transfer is unavailable")
    validate_grant(
        connection,
        actor_user_id,
        proposal.authorising_grant_id,
        proposal.expected_grant_version,
        proposal.source_unit_id,
        now,
    )
    if (
        ownership["state"] != "active"
        or int(ownership["version"]) != proposal.expected_ownership_version
    ):
        raise WorkflowLegTransferConflict("workflow-leg ownership evidence changed")
    if proposal.expires_at <= now or proposal.expires_at > now + timedelta(days=30):
        raise WorkflowLegTransferConflict("proposal expiry must be within the next 30 days")
    ticket_row, ticket = _ticket(connection, proposal.ticket_id, lock)
    if lock:
        ownership = (
            connection.execute(text(_OWNERSHIP + " FOR UPDATE"), ownership_values)
            .mappings()
            .first()
        )
        if ownership is None or ownership["owning_unit_id"] != proposal.source_unit_id:
            raise WorkflowLegTransferDenied("workflow-leg transfer is unavailable")
        if (
            ownership["state"] != "active"
            or int(ownership["version"]) != proposal.expected_ownership_version
        ):
            raise WorkflowLegTransferConflict("workflow-leg ownership evidence changed")
    if (
        int(ticket_row["version"]) != proposal.expected_ticket_version
        or ticket_row["canonical_hash"] != proposal.expected_ticket_source_hash
        or ticket.state not in {TicketState.ANALYST_IN_PROGRESS, TicketState.REWORK_REQUIRED}
        or not _has_source_assignment(ticket, proposal)
    ):
        raise WorkflowLegTransferDenied("workflow-leg transfer is unavailable")
    packages = tuple(
        connection.execute(
            text(_PACKAGES + (" FOR UPDATE" if lock else "")),
            {"ticket_id": proposal.ticket_id, "workflow_leg": proposal.workflow_leg.value},
        ).mappings()
    )
    _validate_package_inventory(proposal, packages)
    dependencies = tuple(
        connection.execute(
            text(_DEPENDENCIES + (" FOR UPDATE" if lock else "")),
            {"package_ids": [row["package_id"] for row in packages]},
        ).mappings()
    )
    _validate_dependency_dispositions(proposal, dependencies)
    inventory = {
        "ownership": [str(ownership["ownership_id"]), int(ownership["version"])],
        "ticket": [int(ticket_row["version"]), ticket_row["canonical_hash"]],
        "packages": [
            [
                str(row["package_id"]),
                row["state"],
                int(row["version"]),
                str(row["accountable_user_id"]),
            ]
            for row in packages
        ],
        "dependencies": [
            [str(row["package_id"]), str(row["predecessor_package_id"])] for row in dependencies
        ],
    }
    digest = preview_hash(actor_user_id, proposal, inventory)
    return (
        WorkflowLegTransferPreview(
            digest,
            proposal.transfer_id,
            proposal.ticket_id,
            proposal.source_unit_id,
            proposal.target_unit_id,
            len(packages),
            sum(
                item.disposition is PackageTransferDisposition.TRANSFER
                for item in proposal.packages
            ),
            proposal.expires_at,
        ),
        ownership,
        packages,
    )


def validate_grant(
    connection: Connection,
    actor_user_id: UUID,
    grant_id: UUID,
    expected_version: int,
    unit_id: UUID,
    now: datetime,
    action: ManagementAction = ManagementAction.TASK_TRANSFER,
) -> RowMapping:
    row = (
        connection.execute(
            text(_GRANT),
            {"grant_id": grant_id, "actor_id": actor_user_id, "at": now},
        )
        .mappings()
        .first()
    )
    if row is None or int(row["version"]) != expected_version:
        raise WorkflowLegTransferDenied("current task transfer authority is required")
    try:
        validate_lineage(connection, grant_id, actor_user_id, unit_id, action, now)
    except OrganisationAuthorityDenied as exc:
        raise WorkflowLegTransferDenied("current task transfer authority is required") from exc
    return row


def validate_target(
    connection: Connection,
    target_user_id: UUID,
    target_unit_id: UUID,
    membership_id: UUID,
    membership_version: int,
    credential_version: int,
    source_hash: str,
    start: datetime,
    end: datetime,
) -> None:
    if principal_kind(target_user_id) is not PrincipalKind.HUMAN:
        raise WorkflowLegTransferDenied("target analyst is unavailable")
    account = (
        connection.execute(
            text("""SELECT * FROM identity_account_projection
WHERE user_id=:user_id FOR UPDATE"""),
            {"user_id": target_user_id},
        )
        .mappings()
        .first()
    )
    membership = (
        connection.execute(
            text("""SELECT * FROM team_memberships
WHERE membership_id=:membership_id AND user_id=:user_id AND state='active'
AND assignment_eligible AND valid_from<=:start AND(valid_until IS NULL OR :end<=valid_until)
FOR UPDATE"""),
            {"membership_id": membership_id, "user_id": target_user_id, "start": start, "end": end},
        )
        .mappings()
        .first()
    )
    if (
        account is None
        or not account["is_active"]
        or active_analyst_role() not in account["roles"]
        or int(account["credential_version"]) != credential_version
        or account["source_hash"] != source_hash
        or membership is None
        or membership["unit_id"] != target_unit_id
        or int(membership["version"]) != membership_version
    ):
        raise WorkflowLegTransferDenied("target analyst is unavailable")


def _ticket(connection: Connection, ticket_id: UUID, lock: bool) -> tuple[RowMapping, TicketRecord]:
    row = (
        connection.execute(
            text(_TICKET + (" FOR UPDATE" if lock else "")), {"ticket_id": ticket_id}
        )
        .mappings()
        .first()
    )
    decoded = decode_value(dict(row["payload"])) if row is not None else None
    if row is None or not isinstance(decoded, TicketRecord):
        raise WorkflowLegTransferDenied("workflow-leg transfer is unavailable")
    return row, decoded


def _has_source_assignment(ticket: TicketRecord, proposal: ProposeWorkflowLegTransfer) -> bool:
    if proposal.workflow_leg.value == "qc":
        return ticket.qc_reviewer_user_id is not None
    route = delivery_route_for_leg(proposal.workflow_leg)
    return any(
        item.active and item.route.value == route and item.team_id == proposal.source_unit_id
        for item in ticket.analyst_assignments
    )


def _validate_package_inventory(
    proposal: ProposeWorkflowLegTransfer, packages: tuple[RowMapping, ...]
) -> None:
    plans = {item.package_id: item for item in proposal.packages}
    if set(plans) != {row["package_id"] for row in packages}:
        raise WorkflowLegTransferConflict("every workflow-leg package needs a disposition")
    for row in packages:
        plan = plans[row["package_id"]]
        if (
            int(row["version"]) != plan.expected_version
            or row["owning_unit_id"] != proposal.source_unit_id
        ):
            raise WorkflowLegTransferConflict("work-package evidence changed")
        state = row["state"]
        if plan.disposition is PackageTransferDisposition.RETAIN and state not in {
            "complete",
            "cancelled",
        }:
            raise WorkflowLegTransferConflict("only terminal packages may be retained")
        if plan.disposition is PackageTransferDisposition.COMPLETE and (
            state in {"complete", "cancelled"} or int(row["remaining_minutes"] or 0) != 0
        ):
            raise WorkflowLegTransferConflict("only finished active packages may be completed")
        if plan.disposition in {
            PackageTransferDisposition.TRANSFER,
            PackageTransferDisposition.CANCEL,
        } and state in {"complete", "cancelled"}:
            raise WorkflowLegTransferConflict("terminal packages cannot use that disposition")


def _validate_dependency_dispositions(
    proposal: ProposeWorkflowLegTransfer, dependencies: tuple[RowMapping, ...]
) -> None:
    plans = {item.package_id: item.disposition for item in proposal.packages}
    for row in dependencies:
        predecessor = plans.get(row["predecessor_package_id"])
        dependent = plans.get(row["package_id"])
        if predecessor is PackageTransferDisposition.CANCEL and dependent not in {
            PackageTransferDisposition.CANCEL,
            PackageTransferDisposition.RETAIN,
        }:
            raise WorkflowLegTransferConflict(
                "cancelling a predecessor requires a safe dependent disposition"
            )
