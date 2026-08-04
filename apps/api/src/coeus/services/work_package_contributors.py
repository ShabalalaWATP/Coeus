"""Application service for reviewed contributor lifecycle changes."""

from uuid import UUID

from coeus.application.ports.work_package_contributors import WorkPackageContributorStore
from coeus.domain.work_package_contributors import (
    ChangeContributorCommand,
    ContributorChangePreview,
    ContributorChangeRequest,
    ContributorChangeResult,
)


class WorkPackageContributorService:
    def __init__(self, store: WorkPackageContributorStore) -> None:
        self._store = store

    def preview(
        self, actor_user_id: UUID, request: ContributorChangeRequest
    ) -> ContributorChangePreview:
        return self._store.preview(actor_user_id, request)

    def execute(self, command: ChangeContributorCommand) -> ContributorChangeResult:
        return self._store.execute(command)
