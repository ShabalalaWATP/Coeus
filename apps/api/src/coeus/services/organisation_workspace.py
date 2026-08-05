"""Read service for the actor's home and explicitly managed workspaces."""

from uuid import UUID

from coeus.application.ports.organisation_workspace import OrganisationWorkspaceStore
from coeus.domain.organisation_workspace import OrganisationWorkspacePage


class OrganisationWorkspaceService:
    def __init__(self, store: OrganisationWorkspaceStore) -> None:
        self._store = store

    def list_for_actor(self, actor_user_id: UUID) -> OrganisationWorkspacePage:
        return self._store.list_actor_workspaces(actor_user_id)
