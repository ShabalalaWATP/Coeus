from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.api.organisation_dependencies import get_workspace_productivity
from coeus.core.config import Settings
from coeus.domain.workspace_productivity import (
    DeliveryMode,
    DeliveryPreferences,
    PackageTemplate,
    RecordPage,
    SavedBoardFilters,
    SavedBoardView,
    WorkspaceRecordDenied,
    WorkspaceStoreLink,
    WorkUpdate,
    WorkUpdateKind,
)
from coeus.main import create_app
from rfi_search_helpers import login


class _ProductivityService:
    def __init__(self) -> None:
        self.actor = uuid4()
        self.unit = uuid4()
        self.view = SavedBoardView(
            uuid4(), self.actor, self.unit, "Blocked", SavedBoardFilters(), 1, datetime.now(UTC)
        )
        self.template = PackageTemplate(
            uuid4(),
            self.unit,
            self.actor,
            "Assessment",
            ("Research",),
            60,
            2,
            1,
            datetime.now(UTC),
        )
        self.update = WorkUpdate(
            uuid4(),
            self.actor,
            "assigned:1",
            WorkUpdateKind.ASSIGNMENT,
            self.unit,
            "ticket",
            uuid4(),
            datetime.now(UTC),
        )
        self.command = None
        self.link = WorkspaceStoreLink(
            uuid4(),
            self.actor,
            self.unit,
            "ticket",
            self.update.object_id,
            "product",
            uuid4(),
            "Visible report",
            1,
            datetime.now(UTC),
        )
        self.denied = False

    def _check(self):
        if self.denied:
            raise WorkspaceRecordDenied

    def list_views(self, *_args):
        self._check()
        return RecordPage((self.view,), None)

    def save_view(self, command):
        self.command = command
        return self.view

    def delete_view(self, command):
        self.command = command
        return True

    def list_templates(self, *_args):
        return RecordPage((self.template,), None)

    def save_template(self, command):
        self.command = command
        return self.template

    def delete_template(self, command):
        self.command = command
        return True

    def list_updates(self, *_args):
        return RecordPage((self.update,), None)

    def acknowledge_update(self, command):
        self.command = command
        return self.update

    def get_preferences(self, actor):
        return DeliveryPreferences(actor, DeliveryMode.IMMEDIATE, True, 0)

    def save_preferences(self, command):
        self.command = command
        return DeliveryPreferences(command.actor_user_id, DeliveryMode.DIGEST, False, 1)

    def list_store_links(self, *_args):
        return RecordPage((self.link,), None)

    def save_store_link(self, _actor, command):
        self.command = command
        return self.link

    def delete_store_link(self, command):
        self.command = command
        return True


@pytest.mark.asyncio
async def test_workspace_productivity_contracts_are_actor_scoped_and_csrf_protected() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    service = _ProductivityService()
    app.dependency_overrides[get_workspace_productivity] = lambda: service
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        assert (await client.get("/api/v1/organisation/saved-board-views")).status_code == 401
        session = await login(client, "user@example.test")
        csrf = {"X-CSRF-Token": session["csrfToken"]}
        assert (await client.get("/api/v1/organisation/saved-board-views")).json()["items"][0][
            "name"
        ] == "Blocked"
        unit = service.unit
        common = {"commandId": str(uuid4()), "idempotencyKey": str(uuid4())}
        view_response = await client.put(
            f"/api/v1/organisation/workspaces/{unit}/saved-board-views",
            headers=csrf,
            json={
                **common,
                "viewId": str(service.view.view_id),
                "name": "Blocked",
                "expectedVersion": 0,
                "filters": {"scope": "direct"},
            },
        )
        assert view_response.status_code == 200
        assert service.command.payload["unit_id"] == unit
        assert (
            await client.get(f"/api/v1/organisation/workspaces/{unit}/package-templates")
        ).status_code == 200
        grant = uuid4()
        template_response = await client.put(
            f"/api/v1/organisation/workspaces/{unit}/package-templates",
            headers=csrf,
            json={
                **common,
                "templateId": str(service.template.template_id),
                "name": "Assessment",
                "packageTitles": ["Research"],
                "expectedVersion": 0,
                "authorisingGrantId": str(grant),
                "expectedGrantVersion": 1,
            },
        )
        assert template_response.status_code == 200
        update_response = await client.get("/api/v1/organisation/work-updates")
        assert update_response.json()["items"][0]["kind"] == "assignment"
        untrusted_delivery = await client.post(
            f"/api/v1/organisation/workspaces/{unit}/work-update-deliveries",
            headers=csrf,
            json={"recipientUserId": str(service.actor), "kind": "assignment"},
        )
        assert untrusted_delivery.status_code == 404
        preferences = await client.get("/api/v1/organisation/work-update-preferences")
        assert preferences.json()["mode"] == "immediate"
        saved = await client.put(
            "/api/v1/organisation/work-update-preferences",
            headers=csrf,
            json={
                **common,
                "mode": "digest",
                "dueReminders": False,
                "expectedVersion": 0,
            },
        )
        assert saved.json() == {"mode": "digest", "dueReminders": False, "version": 1}
        links_path = f"/api/v1/organisation/workspaces/{unit}/store-links"
        links = await client.get(
            links_path,
            params={"sourceType": "ticket", "sourceId": str(service.update.object_id)},
        )
        assert links.json()["items"][0]["label"] == "Visible report"
        linked = await client.put(
            links_path,
            headers=csrf,
            json={
                **common,
                "linkId": str(service.link.link_id),
                "sourceType": "ticket",
                "sourceId": str(service.update.object_id),
                "targetType": "product",
                "targetId": str(service.link.target_id),
                "expectedVersion": 0,
            },
        )
        assert linked.status_code == 200


@pytest.mark.asyncio
async def test_inaccessible_saved_views_use_the_generic_not_found_posture() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    service = _ProductivityService()
    service.denied = True
    app.dependency_overrides[get_workspace_productivity] = lambda: service
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "user@example.test")
        response = await client.get("/api/v1/organisation/saved-board-views")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "workspace_record_not_found"
