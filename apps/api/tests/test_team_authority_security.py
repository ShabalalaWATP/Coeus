from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login


def _app() -> FastAPI:
    return create_app(Settings(environment="test", argon2_memory_cost=8_192))


def _user_id(app: FastAPI, username: str) -> str:
    user = app.state.access_services.repository.get_user_by_username(username)
    assert user is not None
    return str(user.user_id)


async def _team_id(client: AsyncClient, name: str) -> str:
    response = await client.get("/api/v1/teams")
    assert response.status_code == 200
    return next(team["id"] for team in response.json()["teams"] if team["name"] == name)


@pytest.mark.asyncio
async def test_switching_manager_domain_does_not_restore_old_team_authority() -> None:
    app = _app()
    entry_date = (datetime.now(UTC).date() + timedelta(days=5)).isoformat()
    rfa_manager_id = _user_id(app, "rfa.manager@example.test")
    rfa_target_id = _user_id(app, "analyst.4@example.test")
    cm_target_id = _user_id(app, "collection.team@example.test")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        rfa_manager = await login(client, "rfa.manager@example.test")
        rfa_team_id = await _team_id(client, "RFA Assessment Team")
        current_rfa_write = await client.post(
            f"/api/v1/teams/{rfa_team_id}/calendar",
            headers={"X-CSRF-Token": str(rfa_manager["csrfToken"])},
            json={"userId": rfa_target_id, "date": entry_date, "status": "leave"},
        )

        admin = await login(client, "admin@example.test")
        demoted = await client.put(
            f"/api/v1/admin/users/{rfa_manager_id}/roles",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
            json={"roles": ["Customer"]},
        )
        promoted_elsewhere = await client.put(
            f"/api/v1/admin/users/{rfa_manager_id}/roles",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
            json={"roles": ["CM Manager"]},
        )

        switched_manager = await login(client, "rfa.manager@example.test")
        stale_rfa_write = await client.post(
            f"/api/v1/teams/{rfa_team_id}/calendar",
            headers={"X-CSRF-Token": str(switched_manager["csrfToken"])},
            json={"userId": rfa_target_id, "date": entry_date, "status": "on_task"},
        )

        cm_manager = await login(client, "collection.manager@example.test")
        cm_team_id = await _team_id(client, "Collection Management Team")
        current_cm_write = await client.post(
            f"/api/v1/teams/{cm_team_id}/calendar",
            headers={"X-CSRF-Token": str(cm_manager["csrfToken"])},
            json={"userId": cm_target_id, "date": entry_date, "status": "on_task"},
        )

    assert current_rfa_write.status_code == 200
    assert demoted.status_code == 200
    assert promoted_elsewhere.status_code == 200
    assert stale_rfa_write.status_code == 403
    assert current_cm_write.status_code == 200
