"""HTTP contract tests for the separately gated organisation management plane."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.api.organisation_dependencies import get_organisation_administration
from coeus.core.config import Settings
from coeus.domain.organisation import OrganisationCategory, OrganisationUnit
from coeus.domain.organisation_bootstrap import OrganisationBootstrapResult
from coeus.domain.organisation_lifecycle import (
    OrganisationMutationCommand,
    OrganisationMutationConflict,
    OrganisationMutationOperation,
    OrganisationMutationPreview,
    OrganisationMutationResult,
)
from coeus.main import create_app
from coeus.services.organisation_bootstrap import OrganisationBootstrapService
from rfi_search_helpers import login


class _Repository:
    def __init__(self, root: OrganisationUnit, child: OrganisationUnit) -> None:
        self.root = root
        self.child = child

    def list_roots(self):  # type: ignore[no-untyped-def]
        return (self.root,)

    def list_children(self, unit_id: UUID):  # type: ignore[no-untyped-def]
        return (self.child,) if unit_id == self.root.unit_id else ()

    def get_unit(self, unit_id: UUID):  # type: ignore[no-untyped-def]
        return next((unit for unit in (self.root, self.child) if unit.unit_id == unit_id), None)


class _Lifecycle:
    def __init__(self) -> None:
        self.preview_request = None
        self.command: OrganisationMutationCommand | None = None
        self.conflict = False

    def preview(self, request, actor_id):  # type: ignore[no-untyped-def]
        if self.conflict:
            raise OrganisationMutationConflict("Synthetic stale unit.")
        self.preview_request = request
        return OrganisationMutationPreview(
            request.operation,
            request.unit_id,
            request.parent_unit_id,
            request.expected_version,
            "a" * 64,
        )

    def execute(self, command: OrganisationMutationCommand) -> OrganisationMutationResult:
        self.command = command
        return OrganisationMutationResult(command.request.unit_id, 1, uuid4())


class _BootstrapStore:
    def __init__(self) -> None:
        self.plan = None

    def bootstrap(self, plan):  # type: ignore[no-untyped-def]
        self.plan = plan
        return OrganisationBootstrapResult(plan.root_unit_id, uuid4(), (uuid4(),))


BOOTSTRAP_NONCE = "synthetic-bootstrap-api-nonce-123456"


def _app():  # type: ignore[no-untyped-def]
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    root = OrganisationUnit(
        uuid4(),
        "Synthetic Root",
        "Root",
        OrganisationCategory.COMMAND,
        None,
        datetime(2026, 8, 3, tzinfo=UTC),
    )
    child = OrganisationUnit(
        uuid4(),
        "Synthetic Child",
        "Child",
        OrganisationCategory.DELIVERY_TEAM,
        root.unit_id,
        datetime(2026, 8, 3, tzinfo=UTC),
    )
    lifecycle = _Lifecycle()
    administration = SimpleNamespace(
        repository=_Repository(root, child),
        lifecycle=lifecycle,
        bootstrap=OrganisationBootstrapService(_BootstrapStore(), BOOTSTRAP_NONCE),
    )
    app.dependency_overrides[get_organisation_administration] = lambda: administration
    return app, root, child, lifecycle


def _bootstrap_payload() -> dict[str, object]:
    return {
        "commandId": str(uuid4()),
        "rootUnitId": str(uuid4()),
        "rootName": "Synthetic Defence Intelligence",
        "rootShortName": "Synthetic DI",
        "timeZone": "Europe/London",
        "description": "Synthetic administration contract.",
        "currentPassword": "CoeusLocal1!",
        "setupNonce": BOOTSTRAP_NONCE,
    }


def _payload(parent_id: UUID) -> dict[str, object]:
    return {
        "operation": "create",
        "unitId": str(uuid4()),
        "parentId": str(parent_id),
        "expectedVersion": 1,
        "name": "New Synthetic Team",
        "shortName": "New Team",
        "category": "delivery_team",
        "timeZone": "Europe/London",
        "description": "Synthetic administration contract.",
        "authorisingGrantId": str(uuid4()),
        "reason": "Create a synthetic delivery team.",
    }


@pytest.mark.asyncio
async def test_admin_lists_tree_and_runs_preview_execute_contract() -> None:
    app, root, child, lifecycle = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        roots = await client.get("/api/v1/admin/organisation/units")
        children = await client.get(
            "/api/v1/admin/organisation/units", params={"parentId": str(root.unit_id)}
        )
        selected = await client.get(f"/api/v1/admin/organisation/units/{child.unit_id}")
        assert roots.status_code == children.status_code == selected.status_code == 200
        assert roots.json()["units"][0]["id"] == str(root.unit_id)
        assert children.json()["units"][0]["id"] == str(child.unit_id)
        assert selected.json()["name"] == child.name
        payload = _payload(root.unit_id)
        preview = await client.post(
            "/api/v1/admin/organisation/unit-previews",
            headers={"X-CSRF-Token": session["csrfToken"]},
            json=payload,
        )
        assert preview.status_code == 200
        assert preview.json()["previewHash"] == "a" * 64
        command_id = uuid4()
        executed = await client.post(
            "/api/v1/admin/organisation/unit-commands",
            headers={"X-CSRF-Token": session["csrfToken"]},
            json={
                "commandId": str(command_id),
                "idempotencyKey": "create-new-synthetic-team",
                "previewHash": preview.json()["previewHash"],
                "request": payload,
            },
        )
        assert executed.status_code == 200
        assert executed.json()["unitId"] == payload["unitId"]
    assert lifecycle.preview_request.operation is OrganisationMutationOperation.CREATE
    assert lifecycle.command is not None and lifecycle.command.command_id == command_id
    administrator = app.state.access_services.repository.get_user_by_username("admin@example.test")
    assert administrator is not None
    assert lifecycle.command.actor_user_id == administrator.user_id


@pytest.mark.asyncio
async def test_bootstrap_requires_csrf_password_nonce_and_binds_session_actor() -> None:
    app, _, _, _ = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        payload = _bootstrap_payload()
        assert (
            await client.post("/api/v1/admin/organisation/bootstrap", json=payload)
        ).status_code == 403
        wrong_password = await client.post(
            "/api/v1/admin/organisation/bootstrap",
            headers={"X-CSRF-Token": session["csrfToken"]},
            json={**payload, "currentPassword": "wrong-password"},
        )
        assert wrong_password.status_code == 401
        wrong_nonce = await client.post(
            "/api/v1/admin/organisation/bootstrap",
            headers={"X-CSRF-Token": session["csrfToken"]},
            json={**payload, "setupNonce": "x" * 32},
        )
        assert wrong_nonce.status_code == 403
        created = await client.post(
            "/api/v1/admin/organisation/bootstrap",
            headers={"X-CSRF-Token": session["csrfToken"]},
            json=payload,
        )
    assert created.status_code == 200
    assert created.json()["rootUnitId"] == payload["rootUnitId"]
    response_text = created.text
    assert payload["currentPassword"] not in response_text
    assert payload["setupNonce"] not in response_text


@pytest.mark.asyncio
async def test_management_routes_enforce_auth_csrf_permission_and_safe_conflicts() -> None:
    app, root, _, lifecycle = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        assert (await client.get("/api/v1/admin/organisation/units")).status_code == 401
        await login(client, "user@example.test")
        assert (await client.get("/api/v1/admin/organisation/units")).status_code == 403
        session = await login(client, "admin@example.test")
        payload = _payload(root.unit_id)
        assert (
            await client.post("/api/v1/admin/organisation/unit-previews", json=payload)
        ).status_code == 403
        lifecycle.conflict = True
        response = await client.post(
            "/api/v1/admin/organisation/unit-previews",
            headers={"X-CSRF-Token": session["csrfToken"]},
            json=payload,
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "organisation_mutation_conflict"
        invalid = {**payload, "actorUserId": str(uuid4())}
        assert (
            await client.post(
                "/api/v1/admin/organisation/unit-previews",
                headers={"X-CSRF-Token": session["csrfToken"]},
                json=invalid,
            )
        ).status_code == 422


@pytest.mark.asyncio
async def test_disabled_runtime_reports_management_unavailable() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "admin@example.test")
        response = await client.get("/api/v1/admin/organisation/units")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "organisation_management_unavailable"
