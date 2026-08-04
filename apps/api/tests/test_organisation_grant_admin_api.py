"""HTTP contract tests for explicit organisation management grants."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.api.organisation_dependencies import get_organisation_administration
from coeus.core.config import Settings
from coeus.domain.organisation import (
    ManagementAction,
    OrganisationManagementGrant,
)
from coeus.domain.organisation_authority import (
    GrantCommandResult,
    OrganisationAuthorityDenied,
)
from coeus.main import create_app
from rfi_search_helpers import login


class _Repository:
    def __init__(self, grant: OrganisationManagementGrant) -> None:
        self.grant = grant
        self.filters = None

    def list_management_grants(self, **filters):  # type: ignore[no-untyped-def]
        self.filters = filters
        return (self.grant,)


class _Grants:
    def __init__(self) -> None:
        self.created = None
        self.revoked = None
        self.denied = False

    def create(self, command):  # type: ignore[no-untyped-def]
        if self.denied:
            raise OrganisationAuthorityDenied("Synthetic internal grant detail.")
        self.created = command
        return GrantCommandResult(command.grant_id, 1)

    def revoke(self, command):  # type: ignore[no-untyped-def]
        self.revoked = command
        return GrantCommandResult(command.grant_id, command.expected_version + 1)


def _app():  # type: ignore[no-untyped-def]
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    now = datetime.now(UTC)
    grant = OrganisationManagementGrant(
        uuid4(),
        uuid4(),
        uuid4(),
        ManagementAction.ROSTER_MANAGE,
        True,
        now,
        uuid4(),
        "Synthetic grant reason that must not be returned.",
    )
    repository, grants = _Repository(grant), _Grants()
    administration = SimpleNamespace(repository=repository, grants=grants)
    app.dependency_overrides[get_organisation_administration] = lambda: administration
    return app, repository, grants, grant


@pytest.mark.asyncio
async def test_list_create_and_revoke_grant_contract() -> None:
    app, repository, grants, listed_grant = _app()
    manager_id, root_id, source_id, new_grant_id = (uuid4() for _ in range(4))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        response = await client.get(
            "/api/v1/admin/organisation/grants",
            params={
                "rootUnitId": str(root_id),
                "managerUserId": str(manager_id),
                "includeInactive": "true",
            },
        )
        assert response.status_code == 200
        assert response.json()["grants"][0]["id"] == str(listed_grant.grant_id)
        assert "reason" not in response.json()["grants"][0]
        headers = {"X-CSRF-Token": session["csrfToken"]}
        created = await client.post(
            "/api/v1/admin/organisation/grants",
            headers=headers,
            json={
                "commandId": str(uuid4()),
                "grantId": str(new_grant_id),
                "idempotencyKey": "delegate-roster-scope",
                "managerUserId": str(manager_id),
                "rootUnitId": str(root_id),
                "action": "roster:manage",
                "includeDescendants": False,
                "sourceGrantId": str(source_id),
                "expectedSourceVersion": 2,
                "reason": "Delegate synthetic roster scope.",
                "validUntil": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
            },
        )
        assert created.status_code == 200
        assert created.json()["grantId"] == str(new_grant_id)
        revoked = await client.post(
            f"/api/v1/admin/organisation/grants/{new_grant_id}/revoke",
            headers=headers,
            json={
                "commandId": str(uuid4()),
                "idempotencyKey": "revoke-roster-scope",
                "expectedVersion": 1,
                "reason": "Revoke synthetic roster scope.",
            },
        )
        assert revoked.status_code == 200 and revoked.json()["version"] == 2
    assert repository.filters == {
        "root_unit_id": root_id,
        "manager_user_id": manager_id,
        "include_inactive": True,
    }
    actor = app.state.access_services.repository.get_user_by_username("admin@example.test")
    assert actor is not None
    assert grants.created.actor_user_id == grants.revoked.actor_user_id == actor.user_id


@pytest.mark.asyncio
async def test_grant_denial_is_generic() -> None:
    app, _, grants, _ = _app()
    grants.denied = True
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        response = await client.post(
            "/api/v1/admin/organisation/grants",
            headers={"X-CSRF-Token": session["csrfToken"]},
            json={
                "commandId": str(uuid4()),
                "grantId": str(uuid4()),
                "idempotencyKey": "denied-grant",
                "managerUserId": str(uuid4()),
                "rootUnitId": str(uuid4()),
                "action": "task:view",
                "includeDescendants": False,
                "sourceGrantId": str(uuid4()),
                "expectedSourceVersion": 1,
                "reason": "Synthetic denied grant.",
            },
        )
    assert response.status_code == 403
    assert response.json()["error"]["message"] == (
        "You do not have authority to manage this grant."
    )
