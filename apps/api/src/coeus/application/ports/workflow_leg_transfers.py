"""Application port for reviewed cross-team workflow-leg transfers."""

from typing import Protocol
from uuid import UUID

from coeus.domain.workflow_leg_transfers import (
    ProposeWorkflowLegTransfer,
    WorkflowLegTransferCommand,
    WorkflowLegTransferPreview,
    WorkflowLegTransferResult,
)


class WorkflowLegTransferStore(Protocol):
    def preview(
        self, actor_user_id: UUID, proposal: ProposeWorkflowLegTransfer
    ) -> WorkflowLegTransferPreview: ...

    def propose(
        self,
        actor_user_id: UUID,
        command_id: UUID,
        idempotency_key: str,
        proposal: ProposeWorkflowLegTransfer,
        expected_preview_hash: str,
    ) -> WorkflowLegTransferResult: ...

    def decide(self, command: WorkflowLegTransferCommand) -> WorkflowLegTransferResult: ...
