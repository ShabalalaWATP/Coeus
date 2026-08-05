"""Automatic, bounded transfer-request work-update production."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.work_update_events import WorkUpdateEvent
from coeus.domain.workflow_leg_transfers import ProposeWorkflowLegTransfer
from coeus.domain.workspace_productivity import WorkUpdateKind
from coeus.persistence.organisation_authority_validation import validate_lineage
from coeus.persistence.work_update_outbox_producer import append_work_update_request


def append_transfer_request_updates(
    connection: Connection,
    proposal: ProposeWorkflowLegTransfer,
    actor_user_id: UUID,
    occurred_at: datetime,
) -> int:
    rows = tuple(
        connection.execute(
            text(
                "SELECT grant_id,manager_user_id,root_unit_id FROM team_management_grants "
                "WHERE action=:action AND valid_from<=:at "
                "AND(valid_until IS NULL OR :at<valid_until) "
                "AND(revoked_at IS NULL OR :at<revoked_at) ORDER BY grant_id LIMIT 201"
            ),
            {"action": ManagementAction.TASK_TRANSFER.value, "at": occurred_at},
        ).mappings()
    )
    if len(rows) > 200:
        raise ValueError("transfer notification authority exceeds the bounded cohort")
    produced = 0
    for row in rows:
        grant_id = UUID(str(row["grant_id"]))
        recipient = UUID(str(row["manager_user_id"]))
        root_unit = UUID(str(row["root_unit_id"]))
        try:
            validate_lineage(
                connection,
                grant_id,
                recipient,
                proposal.target_unit_id,
                ManagementAction.TASK_TRANSFER,
                occurred_at,
            )
        except OrganisationAuthorityDenied:
            continue
        append_work_update_request(
            connection,
            causation_id=proposal.transfer_id,
            aggregate_version=1,
            actor_user_id=actor_user_id,
            event=WorkUpdateEvent(
                recipient,
                WorkUpdateKind.TRANSFER_REQUEST,
                root_unit,
                "grant",
                grant_id,
            ),
            occurred_at=occurred_at,
        )
        produced += 1
    return produced
