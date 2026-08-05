"""Application service for explicit predecessor cancellation."""

from uuid import UUID

from coeus.application.ports.package_predecessor_cancellation import (
    PredecessorCancellationStore,
)
from coeus.domain.package_predecessor_cancellation import (
    CancelPredecessorCommand,
    PredecessorCancellationPreview,
    PredecessorCancellationRequest,
    PredecessorCancellationResult,
)


class PredecessorCancellationService:
    def __init__(self, store: PredecessorCancellationStore) -> None:
        self._store = store

    def preview(
        self, actor_user_id: UUID, request: PredecessorCancellationRequest
    ) -> PredecessorCancellationPreview:
        return self._store.preview(actor_user_id, request)

    def execute(self, command: CancelPredecessorCommand) -> PredecessorCancellationResult:
        return self._store.execute(command)
