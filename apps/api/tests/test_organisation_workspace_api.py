"""HTTP contract tests for ordinary organisation workspace discovery."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.api.organisation_dependencies import get_organisation_workspace
from coeus.core.config import Settings
from coeus.domain.organisation import OrganisationCategory, OrganisationUnit
from coeus.domain.organisation_workspace import (
    OrganisationWorkspace,
    OrganisationWorkspaceIntegrityError,
    OrganisationWorkspacePage,
    WorkspaceRelationship,
)
from coeus.main import create_app
from rfi_search_helpers import login


class _WorkspaceService:
    def __init__(self, workspace: OrganisationWorkspace) -> None:
        self.workspace = workspace
        self.actor_id = None
        self.integrity_error = False

    def list_for_actor(self, actor_id):  # type: ignore[no-untyped-def]
        self.actor_id = actor_id
        if self.integrity_error:
            raise OrganisationWorkspaceIntegrityError("synthetic duplicate home")
        return OrganisationWorkspacePage(
            (self.workspace,), datetime(2026, 8, 3, 12, tzinfo=UTC), False
        )


@pytest.mark.asyncio
async def test_workspace_list_is_authenticated_actor_scoped_and_camel_case() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    unit = OrganisationUnit(
        uuid4(),
        "Synthetic Analysis Team",
        "SYN-AT",
        OrganisationCategory.DELIVERY_TEAM,
        uuid4(),
        datetime(2026, 8, 3, tzinfo=UTC),
    )
    service = _WorkspaceService(
        OrganisationWorkspace(
            unit, WorkspaceRelationship.HOME, False, False, True, False, False, None
        )
    )
    app.dependency_overrides[get_organisation_workspace] = lambda: service
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        assert (await client.get("/api/v1/organisation/workspaces")).status_code == 401
        await login(client, "user@example.test")
        response = await client.get("/api/v1/organisation/workspaces")
    assert response.status_code == 200
    assert response.json() == {
        "workspaces": [
            {
                "unit": {
                    "id": str(unit.unit_id),
                    "name": unit.name,
                    "shortName": unit.short_name,
                    "category": "delivery_team",
                    "timeZone": "Europe/London",
                },
                "relationship": "home",
                "managed": False,
                "includeDescendants": False,
                "canViewAvailability": True,
                "canViewDetail": False,
                "canViewTasks": False,
                "canViewPeople": False,
                "canViewCapabilities": False,
                "canConfigure": False,
                "planningGrantId": None,
                "configurationGrantId": None,
                "configurationGrantVersion": None,
                "calendarManagementGrantId": None,
                "exportGrantId": None,
                "exportGrantVersion": None,
            }
        ],
        "asOf": "2026-08-03T12:00:00Z",
        "truncated": False,
    }
    actor = app.state.access_services.repository.get_user_by_username("user@example.test")
    assert actor is not None and service.actor_id == actor.user_id


@pytest.mark.asyncio
async def test_disabled_runtime_does_not_expose_workspace_records() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "user@example.test")
        response = await client.get("/api/v1/organisation/workspaces")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "organisation_management_unavailable"


@pytest.mark.asyncio
async def test_workspace_integrity_failure_is_generic() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    unit = OrganisationUnit(
        uuid4(),
        "Synthetic Team",
        "SYN",
        OrganisationCategory.DELIVERY_TEAM,
        None,
        datetime(2026, 8, 3, tzinfo=UTC),
    )
    service = _WorkspaceService(
        OrganisationWorkspace(
            unit, WorkspaceRelationship.HOME, False, False, False, False, False, None
        )
    )
    service.integrity_error = True
    app.dependency_overrides[get_organisation_workspace] = lambda: service
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "user@example.test")
        response = await client.get("/api/v1/organisation/workspaces")
    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "organisation_workspace_unavailable",
            "message": "Your organisation workspace is temporarily unavailable.",
        }
    }
