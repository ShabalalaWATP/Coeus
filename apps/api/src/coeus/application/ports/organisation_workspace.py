"""Persistence boundary for actor-scoped organisation workspaces."""

from typing import Protocol
from uuid import UUID

from coeus.domain.organisation_workspace import OrganisationWorkspacePage


class OrganisationWorkspaceStore(Protocol):
    def list_actor_workspaces(self, actor_user_id: UUID) -> OrganisationWorkspacePage: ...
