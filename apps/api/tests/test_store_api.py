import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app

SEED_CREDENTIAL = "CoeusLocal1!"


async def login(client: AsyncClient, username: str) -> dict[str, object]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": SEED_CREDENTIAL},
    )
    assert response.status_code == 200
    return response.json()


def product_payload(acg_id: str, *, owner_team: str = "RFA") -> dict[str, object]:
    return {
        "title": "Mock Harbour Activity Brief",
        "summary": "MOCK DATA ONLY assessment of harbour activity.",
        "description": "Synthetic product metadata for Sprint 5 testing.",
        "productType": "assessment_report",
        "sourceType": "finished_assessment",
        "ownerTeam": owner_team,
        "areaOrRegion": "Baltic ports",
        "classificationLevel": 2,
        "releasability": ["MOCK"],
        "handlingCaveats": ["MOCK DATA ONLY"],
        "tags": ["ports", "activity"],
        "acgIds": [acg_id],
        "assets": [
            {
                "name": "harbour-brief.pdf",
                "assetType": "pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 42_000,
                "sha256": "a" * 64,
            }
        ],
    }


@pytest.mark.asyncio
async def test_admin_can_create_existing_product_and_search_metadata() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    acg_id = str(app.state.access_services.repository.list_acgs()[0].acg_id)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        created = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json=product_payload(acg_id),
        )
        search = await client.get("/api/v1/store/products", params={"query": "harbour"})
        audit = await client.get("/api/v1/audit")

    assert created.status_code == 201
    payload = created.json()
    assert payload["title"] == "Mock Harbour Activity Brief"
    assert payload["assets"][0]["sha256"] == "a" * 64
    assert "objectKey" not in payload["assets"][0]
    assert search.status_code == 200
    assert any(item["title"] == "Mock Harbour Activity Brief" for item in search.json()["products"])
    assert "product_created" in [event["eventType"] for event in audit.json()["events"]]


@pytest.mark.asyncio
async def test_product_creation_requires_active_authorised_acg() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    collection_acg = next(
        acg for acg in app.state.access_services.repository.list_acgs() if "BRAVO" in acg.code
    )
    rfa_acg = next(
        acg for acg in app.state.access_services.repository.list_acgs() if "CHARLIE" in acg.code
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "rfa.team@example.test")
        denied = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json=product_payload(str(collection_acg.acg_id)),
        )
        allowed = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json=product_payload(str(rfa_acg.acg_id)),
        )
        wrong_owner_team = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json=product_payload(str(rfa_acg.acg_id), owner_team="Collection"),
        )
        missing_acg = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={**product_payload(str(rfa_acg.acg_id)), "acgIds": []},
        )

    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "acg_not_authorised"
    assert allowed.status_code == 201
    assert wrong_owner_team.status_code == 403
    assert wrong_owner_team.json()["error"]["code"] == "forbidden"
    assert missing_acg.status_code == 409
    assert missing_acg.json()["error"]["code"] == "product_acg_required"


@pytest.mark.asyncio
async def test_search_filters_after_access_checks_without_count_leakage() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "user@example.test")
        all_products = await client.get("/api/v1/store/products")
        collection_query = await client.get(
            "/api/v1/store/products",
            params={"query": "collection", "sourceType": "sensor"},
        )
        regional_filter = await client.get(
            "/api/v1/store/products",
            params={"productType": "assessment_report", "tag": "regional", "region": "Baltic"},
        )

    assert all_products.status_code == 200
    assert all_products.json()["total"] == 1
    assert [product["title"] for product in all_products.json()["products"]] == [
        "Regional Stability Brief"
    ]
    assert collection_query.json()["total"] == 0
    assert collection_query.json()["facets"]["productTypes"] == []
    assert regional_filter.json()["total"] == 1


@pytest.mark.asyncio
async def test_product_detail_and_asset_access_are_object_authorised() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    collection_product = next(
        product
        for product in app.state.store_services.repository.list_products()
        if product.metadata.owner_team == "Collection"
    )
    regional_product = next(
        product
        for product in app.state.store_services.repository.list_products()
        if product.metadata.title == "Regional Stability Brief"
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "user@example.test")
        denied_detail = await client.get(f"/api/v1/store/products/{collection_product.product_id}")
        asset_id = regional_product.assets[0].asset_id
        allowed_asset = await client.get(
            f"/api/v1/store/products/{regional_product.product_id}/assets/{asset_id}/access"
        )
        denied_asset = await client.get(
            f"/api/v1/store/products/{collection_product.product_id}/assets/"
            f"{collection_product.assets[0].asset_id}/access"
        )

    assert denied_detail.status_code == 404
    assert denied_detail.json()["error"]["code"] == "product_not_found"
    assert allowed_asset.status_code == 200
    assert allowed_asset.json()["downloadToken"].startswith("asset-token-")
    assert "objectKey" not in allowed_asset.json()
    assert denied_asset.status_code == 404


@pytest.mark.asyncio
async def test_metadata_suggestions_do_not_assign_acgs() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        response = await client.post(
            "/api/v1/store/metadata-suggestions",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={
                "title": "Mock Baltic Port GeoJSON Layer",
                "summary": "MOCK DATA ONLY geography layer for Baltic ports.",
                "productType": "geographic_product",
                "areaOrRegion": "Baltic ports",
            },
        )

    assert response.status_code == 200
    assert response.json()["tags"] == ["baltic", "geographic", "mock"]
    assert response.json()["entities"]
    assert response.json()["acgIds"] == []


@pytest.mark.asyncio
async def test_invalid_asset_hash_and_geographic_metadata_are_rejected() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    acg_id = str(app.state.access_services.repository.list_acgs()[0].acg_id)
    invalid_hash = product_payload(acg_id)
    invalid_hash["assets"] = [
        {
            "name": "bad.pdf",
            "assetType": "pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 42,
            "sha256": "not-a-hash",
        }
    ]
    invalid_geo = {
        **product_payload(acg_id),
        "productType": "geographic_product",
        "geojsonRef": None,
        "boundingBox": None,
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        bad_hash = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json=invalid_hash,
        )
        bad_geo = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json=invalid_geo,
        )

    assert bad_hash.status_code == 409
    assert bad_hash.json()["error"]["code"] == "asset_hash_invalid"
    assert bad_geo.status_code == 409
    assert bad_geo.json()["error"]["code"] == "geographic_metadata_required"
