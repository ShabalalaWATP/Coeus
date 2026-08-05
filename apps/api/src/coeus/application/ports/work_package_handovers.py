"""Application port for canonical accountable-owner handover."""

from typing import Protocol
from uuid import UUID

from coeus.domain.work_package_handovers import (
    HandoverWorkPackageCommand,
    WorkPackageHandoverPreview,
    WorkPackageHandoverRequest,
    WorkPackageHandoverResult,
)


class WorkPackageHandoverStore(Protocol):
    def preview(
        self, actor_user_id: UUID, request: WorkPackageHandoverRequest
    ) -> WorkPackageHandoverPreview: ...

    def execute(self, command: HandoverWorkPackageCommand) -> WorkPackageHandoverResult: ...
