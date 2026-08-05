"""HTTP contract tests for the admin-only calendar import."""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.api.organisation_dependencies import get_calendar_import
from coeus.core.config import Settings
from coeus.domain.calendar_import import (
    CalendarImportConflict,
    CalendarImportPreview,
    CalendarImportResult,
)
from coeus.main import create_app
from rfi_search_helpers import login


class _Service:
    def __init__(self) -> None:
        self.command = None

    def preview(self, actor_id):  # type: ignore[no-untyped-def]
        del actor_id
        return CalendarImportPreview("a" * 64, "b" * 64, "c" * 64, 3, 2, 1, ())

    def apply(self, command):  # type: ignore[no-untyped-def]
        self.command = command
        return CalendarImportResult(command.command_id, 2, 1, False)


@pytest.mark.asyncio
async def test_admin_can_preview_and_apply_calendar_import() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    service = _Service()
    app.dependency_overrides[get_calendar_import] = lambda: service
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        headers = {"X-CSRF-Token": session["csrfToken"]}
        preview = await client.post(
            "/api/v1/admin/organisation/calendar-import/preview", headers=headers
        )
        command_id = uuid4()
        result = await client.post(
            "/api/v1/admin/organisation/calendar-import/commands",
            headers=headers,
            json={
                "commandId": str(command_id),
                "idempotencyKey": "legacy-import",
                "previewHash": preview.json()["previewHash"],
            },
        )
    assert preview.status_code == 200 and preview.json()["importableCount"] == 2
    assert result.status_code == 200 and result.json()["importedCount"] == 2
    assert service.command.command_id == command_id


@pytest.mark.asyncio
async def test_non_admin_and_conflict_are_bounded() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    service = _Service()
    app.dependency_overrides[get_calendar_import] = lambda: service
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        denied = await client.post(
            "/api/v1/admin/organisation/calendar-import/preview",
            headers={"X-CSRF-Token": user["csrfToken"]},
        )
        admin = await login(client, "admin@example.test")
        service.preview = lambda actor_id: (_ for _ in ()).throw(  # type: ignore[method-assign]
            CalendarImportConflict("synthetic collision")
        )
        conflict = await client.post(
            "/api/v1/admin/organisation/calendar-import/preview",
            headers={"X-CSRF-Token": admin["csrfToken"]},
        )
    assert denied.status_code == 403
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "calendar_import_conflict"
