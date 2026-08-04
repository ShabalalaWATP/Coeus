"""Application service for reviewed work-package dependency commands."""

from uuid import UUID

from coeus.application.ports.work_package_dependencies import WorkPackageDependencyStore
from coeus.domain.work_package_dependencies import (
    ChangeDependencyCommand,
    DependencyChangePreview,
    DependencyChangeRequest,
    DependencyChangeResult,
)


class WorkPackageDependencyService:
    def __init__(self, store: WorkPackageDependencyStore) -> None:
        self._store = store

    def preview(
        self, actor_user_id: UUID, request: DependencyChangeRequest
    ) -> DependencyChangePreview:
        return self._store.preview(actor_user_id, request)

    def execute(self, command: ChangeDependencyCommand) -> DependencyChangeResult:
        return self._store.execute(command)
