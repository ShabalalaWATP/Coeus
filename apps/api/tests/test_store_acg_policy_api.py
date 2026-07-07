from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from store_api_helpers import login, product_payload


@pytest.mark.asyncio
async def test_product_with_multiple_acgs_is_visible_when_user_has_one_acg() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    regional_acg = next(
        acg for acg in app.state.access_services.repository.list_acgs() if "ALPHA" in acg.code
    )
    collection_acg = next(
        acg for acg in app.state.access_services.repository.list_acgs() if "BRAVO" in acg.code
    )
    payload = {
        **product_payload(str(regional_acg.acg_id)),
        "title": "Mock Shared ACG Brief",
        "acgIds": [str(regional_acg.acg_id), str(collection_acg.acg_id)],
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        admin_session = await login(client, "admin@example.test")
        created = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(admin_session["csrfToken"])},
            json=payload,
        )
        await login(client, "user@example.test")
        detail = await client.get(f"/api/v1/store/products/{created.json()['id']}")
        search = await client.get("/api/v1/store/products", params={"query": "Shared ACG"})

    assert created.status_code == 201
    assert detail.status_code == 200
    assert detail.json()["title"] == "Mock Shared ACG Brief"
    assert "Mock Shared ACG Brief" in [product["title"] for product in search.json()["products"]]


@pytest.mark.asyncio
async def test_admin_store_detail_requires_acg_unless_break_glass_is_audited() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        created_acg = await client.post(
            "/api/v1/acgs",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={
                "code": "ACG-BREAK-GLASS",
                "name": "Break Glass Test",
                "description": "Synthetic test access group.",
            },
        )
        created_product = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={
                **product_payload(created_acg.json()["id"]),
                "title": "Mock Break Glass Product",
                "acgIds": [created_acg.json()["id"]],
            },
        )
        normal_detail = await client.get(f"/api/v1/store/products/{created_product.json()['id']}")
        break_glass = await client.post(
            f"/api/v1/store/products/{created_product.json()['id']}/break-glass",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={"reason": "Synthetic support investigation for access-control test."},
        )
        audit = await client.get("/api/v1/audit")

    assert created_acg.status_code == 201
    assert created_product.status_code == 201
    assert normal_detail.status_code == 404
    assert break_glass.status_code == 200
    assert break_glass.json()["title"] == "Mock Break Glass Product"
    events = [
        event
        for event in audit.json()["events"]
        if event["eventType"] == "product_break_glass_accessed"
    ]
    assert events[-1]["metadata"]["product_id"] == created_product.json()["id"]
    assert "support investigation" in events[-1]["metadata"]["reason"]


@pytest.mark.asyncio
async def test_break_glass_rejects_non_admins_and_missing_products() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    product = next(iter(app.state.store_services.repository.list_products()))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user_session = await login(client, "user@example.test")
        forbidden = await client.post(
            f"/api/v1/store/products/{product.product_id}/break-glass",
            headers={"X-CSRF-Token": str(user_session["csrfToken"])},
            json={"reason": "Synthetic access-control regression test."},
        )
        admin_session = await login(client, "admin@example.test")
        missing = await client.post(
            f"/api/v1/store/products/{uuid4()}/break-glass",
            headers={"X-CSRF-Token": str(admin_session["csrfToken"])},
            json={"reason": "Synthetic missing-product regression test."},
        )

    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "product_not_found"


@pytest.mark.asyncio
async def test_asset_access_rejects_missing_asset_after_product_authorisation() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    product = next(iter(app.state.store_services.repository.list_products()))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "admin@example.test")
        response = await client.get(
            f"/api/v1/store/products/{product.product_id}/assets/{uuid4()}/access"
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "asset_not_found"
