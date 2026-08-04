"""Application service for one previewed package-planning command."""

from uuid import UUID

from coeus.application.ports.work_package_planning import WorkPackagePlanningStore
from coeus.domain.work_package_planning import (
    PlanWorkPackageCommand,
    WorkPackagePlanningPreview,
    WorkPackagePlanningResult,
    WorkPackagePlanRequest,
)


class WorkPackagePlanningService:
    def __init__(self, store: WorkPackagePlanningStore) -> None:
        self._store = store

    def preview(
        self, actor_user_id: UUID, request: WorkPackagePlanRequest
    ) -> WorkPackagePlanningPreview:
        return self._store.preview(actor_user_id, request)

    def execute(self, command: PlanWorkPackageCommand) -> WorkPackagePlanningResult:
        return self._store.execute(command)
