"""Application boundary for contributor lifecycle changes."""

from typing import Protocol
from uuid import UUID

from coeus.domain.work_package_contributors import (
    ChangeContributorCommand,
    ContributorChangePreview,
    ContributorChangeRequest,
    ContributorChangeResult,
)


class WorkPackageContributorStore(Protocol):
    def preview(
        self, actor_user_id: UUID, request: ContributorChangeRequest
    ) -> ContributorChangePreview: ...

    def execute(self, command: ChangeContributorCommand) -> ContributorChangeResult: ...
