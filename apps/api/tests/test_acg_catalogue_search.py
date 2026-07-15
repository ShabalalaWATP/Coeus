from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login


@pytest.mark.asyncio
async def test_catalogue_search_filters_before_totals_and_projects_manager_names() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "user@example.test")
        response = await client.get("/api/v1/acgs/catalogue?query=african%20cyber&pageSize=50")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    item = response.json()["acgs"][0]
    assert item["name"] == "African Cyber"
    assert item["managerNames"]
    assert all(isinstance(name, str) for name in item["managerNames"])


@pytest.mark.asyncio
async def test_catalogue_search_never_counts_an_inactive_match() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    repository = app.state.access_services.repository
    acg = next(item for item in repository.list_acgs() if item.name == "African Cyber")
    admin = repository.get_user_by_username("admin@example.test")
    assert admin is not None
    app.state.access_services.acgs.update_acg(admin, UUID(str(acg.acg_id)), is_active=False)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "user@example.test")
        response = await client.get("/api/v1/acgs/catalogue?query=african%20cyber&pageSize=50")

    assert response.status_code == 200
    assert response.json()["acgs"] == []
    assert response.json()["total"] == 0
    assert response.json()["totalPages"] == 0
