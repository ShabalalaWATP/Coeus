"""Application service for reviewed accountable-owner handover."""

from uuid import UUID

from coeus.application.ports.work_package_handovers import WorkPackageHandoverStore
from coeus.domain.work_package_handovers import (
    HandoverWorkPackageCommand,
    WorkPackageHandoverPreview,
    WorkPackageHandoverRequest,
    WorkPackageHandoverResult,
)


class WorkPackageHandoverService:
    def __init__(self, store: WorkPackageHandoverStore) -> None:
        self._store = store

    def preview(
        self, actor_user_id: UUID, request: WorkPackageHandoverRequest
    ) -> WorkPackageHandoverPreview:
        return self._store.preview(actor_user_id, request)

    def execute(self, command: HandoverWorkPackageCommand) -> WorkPackageHandoverResult:
        return self._store.execute(command)
