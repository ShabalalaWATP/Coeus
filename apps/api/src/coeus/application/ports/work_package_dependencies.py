"""Application boundary for reviewed work-package dependency commands."""

from typing import Protocol
from uuid import UUID

from coeus.domain.work_package_dependencies import (
    ChangeDependencyCommand,
    DependencyChangePreview,
    DependencyChangeRequest,
    DependencyChangeResult,
)


class WorkPackageDependencyStore(Protocol):
    def preview(
        self, actor_user_id: UUID, request: DependencyChangeRequest
    ) -> DependencyChangePreview: ...

    def execute(self, command: ChangeDependencyCommand) -> DependencyChangeResult: ...
