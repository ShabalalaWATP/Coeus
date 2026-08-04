"""Application boundary for atomic package planning and capacity reservation."""

from typing import Protocol
from uuid import UUID

from coeus.domain.work_package_planning import (
    PlanWorkPackageCommand,
    WorkPackagePlanningPreview,
    WorkPackagePlanningResult,
    WorkPackagePlanRequest,
)


class WorkPackagePlanningStore(Protocol):
    def preview(
        self, actor_user_id: UUID, request: WorkPackagePlanRequest
    ) -> WorkPackagePlanningPreview: ...

    def execute(self, command: PlanWorkPackageCommand) -> WorkPackagePlanningResult: ...
