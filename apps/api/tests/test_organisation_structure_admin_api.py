"""HTTP contract tests for reparent and deactivation management commands."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.api.organisation_dependencies import get_organisation_administration
from coeus.core.config import Settings
from coeus.domain.organisation_deactivation import (
    OrganisationDeactivationConflict,
    OrganisationDeactivationImpact,
    OrganisationDeactivationPreview,
    OrganisationDeactivationResult,
)
from coeus.domain.organisation_reparent import (
    OrganisationReparentImpact,
    OrganisationReparentPreview,
    OrganisationReparentResult,
)
from coeus.main import create_app
from rfi_search_helpers import login


class _Reparent:
    def __init__(self) -> None:
        self.command = None

    def preview(self, request, actor_id):  # type: ignore[no-untyped-def]
        impact = OrganisationReparentImpact(
            uuid4(), uuid4(), 2, 3, 1, 1, 4, 0, 0, 0, 0, 0, 5, "b" * 64
        )
        return OrganisationReparentPreview(
            request.unit_id, request.new_parent_unit_id, impact, "a" * 64
        )

    def execute(self, command):  # type: ignore[no-untyped-def]
        self.command = command
        return OrganisationReparentResult(
            command.request.unit_id,
            command.request.new_parent_unit_id,
            2,
            uuid4(),
        )


class _Deactivation:
    def __init__(self) -> None:
        self.command = None
        self.conflict = False

    def preview(self, request, actor_id):  # type: ignore[no-untyped-def]
        if self.conflict:
            raise OrganisationDeactivationConflict("Synthetic dependency appeared.")
        impact = OrganisationDeactivationImpact(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, "c" * 64)
        return OrganisationDeactivationPreview(request, impact, "d" * 64)

    def execute(self, command):  # type: ignore[no-untyped-def]
        self.command = command
        return OrganisationDeactivationResult(command.request.unit_id, 2)


def _app():  # type: ignore[no-untyped-def]
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    reparent = _Reparent()
    deactivation = _Deactivation()
    administration = SimpleNamespace(reparent=reparent, deactivation=deactivation)
    app.dependency_overrides[get_organisation_administration] = lambda: administration
    return app, reparent, deactivation


@pytest.mark.asyncio
async def test_reparent_preview_and_execute_bind_authenticated_actor() -> None:
    app, reparent, _ = _app()
    unit_id, parent_id = uuid4(), uuid4()
    request = {
        "unitId": str(unit_id),
        "newParentId": str(parent_id),
        "expectedUnitVersion": 1,
        "expectedParentVersion": 3,
        "authorisingGrantId": str(uuid4()),
        "reason": "Move the synthetic subtree.",
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        preview = await client.post(
            "/api/v1/admin/organisation/reparent-previews",
            headers={"X-CSRF-Token": session["csrfToken"]},
            json=request,
        )
        assert preview.status_code == 200
        assert preview.json()["impact"]["maximumResultDepth"] == 5
        result = await client.post(
            "/api/v1/admin/organisation/reparent-commands",
            headers={"X-CSRF-Token": session["csrfToken"]},
            json={
                "commandId": str(uuid4()),
                "idempotencyKey": "move-synthetic-subtree",
                "previewHash": preview.json()["previewHash"],
                "request": request,
            },
        )
        assert result.status_code == 200
        assert result.json()["parentId"] == str(parent_id)
    actor = app.state.access_services.repository.get_user_by_username("admin@example.test")
    assert actor is not None and reparent.command.actor_user_id == actor.user_id


@pytest.mark.asyncio
async def test_deactivation_preview_execute_and_conflict_contract() -> None:
    app, _, deactivation = _app()
    unit_id = uuid4()
    request = {
        "unitId": str(unit_id),
        "expectedVersion": 1,
        "authorisingGrantId": str(uuid4()),
        "reason": "End the empty synthetic unit.",
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        headers = {"X-CSRF-Token": session["csrfToken"]}
        preview = await client.post(
            "/api/v1/admin/organisation/deactivation-previews",
            headers=headers,
            json=request,
        )
        assert preview.status_code == 200
        assert preview.json()["impact"]["blockingCount"] == 0
        result = await client.post(
            "/api/v1/admin/organisation/deactivation-commands",
            headers=headers,
            json={
                "commandId": str(uuid4()),
                "idempotencyKey": "end-empty-synthetic-unit",
                "previewHash": preview.json()["previewHash"],
                "request": request,
            },
        )
        assert result.status_code == 200 and result.json()["version"] == 2
        deactivation.conflict = True
        conflict = await client.post(
            "/api/v1/admin/organisation/deactivation-previews",
            headers=headers,
            json=request,
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "organisation_structure_conflict"
