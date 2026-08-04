"""Application boundary for predecessor cancellation dispositions."""

from typing import Protocol
from uuid import UUID

from coeus.domain.package_predecessor_cancellation import (
    CancelPredecessorCommand,
    PredecessorCancellationPreview,
    PredecessorCancellationRequest,
    PredecessorCancellationResult,
)


class PredecessorCancellationStore(Protocol):
    def preview(
        self, actor_user_id: UUID, request: PredecessorCancellationRequest
    ) -> PredecessorCancellationPreview: ...

    def execute(self, command: CancelPredecessorCommand) -> PredecessorCancellationResult: ...
