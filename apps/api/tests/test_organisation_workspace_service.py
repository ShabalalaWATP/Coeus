"""Unit contract for the organisation workspace service boundary."""

from datetime import UTC, datetime
from uuid import uuid4

from coeus.domain.organisation_workspace import OrganisationWorkspacePage
from coeus.services.organisation_workspace import OrganisationWorkspaceService


class _Store:
    def __init__(self, page: OrganisationWorkspacePage) -> None:
        self.page = page
        self.actor_id = None

    def list_actor_workspaces(self, actor_id):  # type: ignore[no-untyped-def]
        self.actor_id = actor_id
        return self.page


def test_service_passes_the_authenticated_actor_to_the_atomic_store() -> None:
    actor_id = uuid4()
    page = OrganisationWorkspacePage((), datetime(2026, 8, 3, tzinfo=UTC), False)
    store = _Store(page)

    assert OrganisationWorkspaceService(store).list_for_actor(actor_id) is page
    assert store.actor_id == actor_id
