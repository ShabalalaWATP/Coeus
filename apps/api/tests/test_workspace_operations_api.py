"""HTTP contract and authorisation tests for workspace operations."""

from datetime import UTC, datetime, time, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.api.organisation_dependencies import get_workspace_operations
from coeus.core.config import Settings
from coeus.domain.workspace_operations import (
    CapabilityCoverage,
    PlanningCadence,
    WorkspaceAnalytics,
    WorkspaceExport,
    WorkspaceMetric,
    WorkspaceOperationsDenied,
    WorkspaceOverview,
    WorkspacePersonView,
    WorkspacePolicy,
    WorkspaceScope,
    WorkspaceSearchResult,
)
from coeus.main import create_app

SEED_CREDENTIAL = "CoeusLocal1!"


async def _login(client: AsyncClient, username: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": SEED_CREDENTIAL}
    )
    assert response.status_code == 200
    return response.json()


class _Service:
    def __init__(self) -> None:
        self.unit = uuid4()
        self.denied = False
        self.search_store_only = False
        now = datetime.now(UTC)
        metric = WorkspaceMetric("headcount", "Headcount", 7, "7", WorkspaceScope.DIRECT, "current")
        self.overview_result = WorkspaceOverview(
            self.unit, WorkspaceScope.DIRECT, now, now + timedelta(minutes=15), (metric,), 0, False
        )
        self.policy_result = WorkspacePolicy(
            self.unit, 8, 72, PlanningCadence.WEEKLY, 0, time(9), 60, 1, 1, now
        )
        self.export_result = WorkspaceExport(
            uuid4(), uuid4(), self.unit, False, "ready", 1, now, now + timedelta(hours=24)
        )

    def _allow(self) -> None:
        if self.denied:
            raise WorkspaceOperationsDenied

    def overview(self, *_args):
        self._allow()
        return self.overview_result

    def people(self, *_args):
        self._allow()
        return (WorkspacePersonView(uuid4(), "Synthetic Analyst", "member", True, "37h"),)

    def capabilities(self, *_args):
        self._allow()
        return (CapabilityCoverage("analysis", 2, None, "<5", None, True),)

    def policy(self, *_args):
        self._allow()
        return self.policy_result

    def save_policy(self, command):
        self._allow()
        self.command = command
        return self.policy_result

    def search(self, *_args, store_only=False, offset=0):
        self._allow()
        self.search_store_only = store_only
        self.search_offset = offset
        return (WorkspaceSearchResult("store_project", uuid4(), self.unit, "Project", "Store"),)

    def analytics(self, *_args):
        self._allow()
        result = self.overview_result
        return WorkspaceAnalytics(
            result.unit_id, result.scope, result.generated_at, result.metrics, "Safe"
        )

    def create_export(self, command):
        self._allow()
        self.command = command
        return self.export_result

    def get_export(self, *_args):
        self._allow()
        return self.export_result

    def export_csv(self, *_args):
        self._allow()
        return b"scope,metric\r\ndirect,Headcount\r\n"


@pytest.mark.asyncio
async def test_workspace_operations_require_auth_csrf_and_protect_denials() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    service = _Service()
    app.dependency_overrides[get_workspace_operations] = lambda: service
    root = f"/api/v1/organisation/workspaces/{service.unit}"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        assert (await client.get(root + "/overview")).status_code == 401
        session = await _login(client, "rfa.manager@example.test")
        assert (await client.get(root + "/overview")).json()["metrics"][0]["display"] == "7"
        assert (await client.get(root + "/people?query=Sy")).status_code == 200
        capabilities = await client.get(root + "/capabilities?scope=descendants")
        assert capabilities.json()["items"][0]["suppressed"] is True
        search = await client.get(root + "/search?query=Project&store_only=true")
        assert search.status_code == 200
        assert service.search_store_only is True
        # The domain result already carries its metrics, so the response must
        # replace them rather than pass them a second time.
        analytics = await client.get(root + "/analytics")
        assert analytics.status_code == 200
        assert analytics.json()["metrics"][0]["display"] == "7"
        policy_payload = {
            "commandId": str(uuid4()),
            "idempotencyKey": "policy-1",
            "authorisingGrantId": str(uuid4()),
            "expectedGrantVersion": 1,
            "expectedVersion": 1,
            "expectedDeliveryPolicyVersion": 1,
            "wipLimit": 8,
            "serviceTargetHours": 72,
            "planningCadence": "weekly",
            "planningWeekday": 0,
            "planningLocalTime": "09:00",
            "planningDurationMinutes": 60,
        }
        assert (await client.put(root + "/policy", json=policy_payload)).status_code == 403
        csrf = {"X-CSRF-Token": session["csrfToken"]}
        saved = await client.put(root + "/policy", json=policy_payload, headers=csrf)
        assert saved.status_code == 200
        service.denied = True
        denied = await client.get(root + "/overview")
        assert denied.status_code == 404
        assert denied.json()["error"]["code"] == "team_workspace_not_found"


@pytest.mark.asyncio
async def test_export_contract_is_bounded_actor_scoped_and_non_cacheable() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    service = _Service()
    app.dependency_overrides[get_workspace_operations] = lambda: service
    root = f"/api/v1/organisation/workspaces/{service.unit}"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await _login(client, "rfa.manager@example.test")
        csrf = {"X-CSRF-Token": session["csrfToken"]}
        response = await client.post(
            root + "/exports",
            headers=csrf,
            json={
                "commandId": str(uuid4()),
                "idempotencyKey": "export-1",
                "exportId": str(service.export_result.export_id),
                "includeDescendants": False,
                "authorisingGrantId": str(uuid4()),
                "expectedGrantVersion": 1,
                "format": "csv",
            },
        )
        assert response.status_code == 201
        download = await client.get(
            f"/api/v1/organisation/workspaces/exports/{service.export_result.export_id}/download"
        )
        assert download.status_code == 200
        assert download.headers["cache-control"] == "no-store"
        assert download.headers["x-content-type-options"] == "nosniff"
