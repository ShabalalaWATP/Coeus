"""Domain conversion and safe HTTP errors for cross-team work transfer."""

from collections.abc import Callable
from uuid import UUID

from coeus.core.errors import AppError
from coeus.domain.workflow_leg_transfers import (
    PackageTransferPlan,
    ProposeWorkflowLegTransfer,
    WorkflowLegTransferCommand,
    WorkflowLegTransferConflict,
    WorkflowLegTransferDenied,
)
from coeus.schemas.workflow_leg_transfers import (
    WorkflowLegTransferCommandPayload,
    WorkflowLegTransferProposalPayload,
)


def proposal(
    source_unit_id: UUID, payload: WorkflowLegTransferProposalPayload
) -> ProposeWorkflowLegTransfer:
    return ProposeWorkflowLegTransfer(
        payload.transfer_id,
        payload.ticket_id,
        payload.workflow_leg,
        source_unit_id,
        payload.target_unit_id,
        payload.target_user_id,
        payload.expected_ownership_version,
        payload.expected_ticket_version,
        payload.expected_ticket_source_hash,
        payload.authorising_grant_id,
        payload.expected_grant_version,
        payload.expires_at,
        tuple(PackageTransferPlan(**item.model_dump()) for item in payload.packages),
        payload.reason,
    )


def command(
    transfer_id: UUID, actor_user_id: UUID, payload: WorkflowLegTransferCommandPayload
) -> WorkflowLegTransferCommand:
    return WorkflowLegTransferCommand(
        payload.command_id,
        payload.idempotency_key,
        actor_user_id,
        transfer_id,
        payload.expected_transfer_version,
        payload.action,
        payload.preview_hash,
        payload.grant_id,
        payload.expected_grant_version,
        payload.target_membership_id,
        payload.expected_target_membership_version,
        payload.expected_target_account_credential_version,
        payload.expected_target_account_source_hash,
        payload.assignment_grant_id,
        payload.expected_assignment_grant_version,
        payload.reason,
    )


def call_transfer[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except WorkflowLegTransferDenied as exc:
        raise AppError(
            404, "workflow_leg_transfer_not_found", "Workflow-leg transfer was not found."
        ) from exc
    except WorkflowLegTransferConflict as exc:
        raise AppError(409, "workflow_leg_transfer_conflict", str(exc)) from exc
    except ValueError as exc:
        raise AppError(422, "workflow_leg_transfer_invalid", str(exc)) from exc
