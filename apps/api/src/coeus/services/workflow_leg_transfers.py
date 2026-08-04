"""Application service for two-manager cross-team work transfer."""

from uuid import UUID

from coeus.application.ports.workflow_leg_transfers import WorkflowLegTransferStore
from coeus.domain.workflow_leg_transfers import (
    ProposeWorkflowLegTransfer,
    WorkflowLegTransferCommand,
    WorkflowLegTransferPreview,
    WorkflowLegTransferResult,
)


class WorkflowLegTransferService:
    def __init__(self, store: WorkflowLegTransferStore) -> None:
        self._store = store

    def preview(
        self, actor_user_id: UUID, proposal: ProposeWorkflowLegTransfer
    ) -> WorkflowLegTransferPreview:
        return self._store.preview(actor_user_id, proposal)

    def propose(
        self,
        actor_user_id: UUID,
        command_id: UUID,
        idempotency_key: str,
        proposal: ProposeWorkflowLegTransfer,
        expected_preview_hash: str,
    ) -> WorkflowLegTransferResult:
        return self._store.propose(
            actor_user_id, command_id, idempotency_key, proposal, expected_preview_hash
        )

    def decide(self, command: WorkflowLegTransferCommand) -> WorkflowLegTransferResult:
        return self._store.decide(command)
