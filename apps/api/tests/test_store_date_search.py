import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app

SEED_CREDENTIAL = "CoeusLocal1!"


def _client() -> AsyncClient:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _login_admin(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin@example.test", "password": SEED_CREDENTIAL},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_date_range_filters_products_by_period_overlap() -> None:
    async with _client() as client:
        await _login_admin(client)

        may_only = await client.get("/api/v1/store/products?dateFrom=2026-05-01&dateTo=2026-05-31")
        assert may_only.status_code == 200
        titles = [product["title"] for product in may_only.json()["products"]]
        assert titles == ["Collection Sensor Summary"]

        from_june = await client.get("/api/v1/store/products?dateFrom=2026-06-01")
        june_titles = {product["title"] for product in from_june.json()["products"]}
        assert june_titles == {"Collection Sensor Summary", "Assessment Draft Pack"}

        before_february = await client.get("/api/v1/store/products?dateTo=2026-02-01")
        assert before_february.json()["products"] == []


@pytest.mark.asyncio
async def test_invalid_date_filters_are_rejected() -> None:
    async with _client() as client:
        await _login_admin(client)

        response = await client.get("/api/v1/store/products?dateFrom=yesterday")
        assert response.status_code == 422
