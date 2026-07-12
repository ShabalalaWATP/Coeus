import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from store_api_helpers import login, product_payload


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
    search_product = next(
        item for item in search.json()["products"] if item["title"] == "Mock Harbour Activity Brief"
    )
    assert search_product["title"] == "Mock Harbour Activity Brief"
    assert "product_created" in [event["eventType"] for event in audit.json()["events"]]


@pytest.mark.asyncio
async def test_admin_can_upload_and_download_real_asset_bytes(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    acg_id = str(app.state.access_services.repository.list_acgs()[0].acg_id)
    metadata = product_payload(acg_id)
    metadata.pop("assets")
    content = b"MOCK DATA ONLY uploaded asset bytes"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        created = await client.post(
            "/api/v1/store/products/upload",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            files={
                "asset": ("uploaded-brief.txt", content, "text/plain"),
                "metadata": (None, json.dumps(metadata), "application/json"),
            },
        )
        product = created.json()
        asset = product["assets"][0]
        grant = await client.get(
            f"/api/v1/store/products/{product['id']}/assets/{asset['id']}/access"
        )
        downloaded = await client.get(
            f"/api/v1/store/products/{product['id']}/assets/{asset['id']}/download",
            headers={"X-Asset-Token": grant.json()["downloadToken"]},
        )

    assert created.status_code == 201
    assert asset["sha256"] != "a" * 64
    assert grant.status_code == 200
    assert grant.json()["downloadToken"].startswith("asset-token-")
    assert downloaded.status_code == 200
    assert downloaded.content == content


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
        session = await login(client, "rfa.manager@example.test")
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
        padded_wrong_owner_team = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json=product_payload(str(rfa_acg.acg_id), owner_team="Collection "),
        )
        unknown_owner_team = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json=product_payload(str(rfa_acg.acg_id), owner_team="Unrecognised"),
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
    assert padded_wrong_owner_team.status_code == 403
    assert padded_wrong_owner_team.json()["error"]["code"] == "forbidden"
    assert unknown_owner_team.status_code == 422
    assert unknown_owner_team.json()["error"]["code"] == "owner_team_invalid"
    assert missing_acg.status_code == 409
    assert missing_acg.json()["error"]["code"] == "product_acg_required"


@pytest.mark.asyncio
async def test_store_manager_can_admin_products_without_restricted_read() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    collection_acg = next(
        acg for acg in app.state.access_services.repository.list_acgs() if "BRAVO" in acg.code
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "store.manager@example.test")
        created = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json=product_payload(str(collection_acg.acg_id), owner_team="Collection"),
        )
        hidden_detail = await client.get(f"/api/v1/store/products/{created.json()['id']}")

    assert session["user"]["defaultRoute"] == "/store"
    assert "product:read_restricted" not in session["user"]["permissions"]
    assert created.status_code == 201
    assert hidden_detail.status_code == 404


@pytest.mark.asyncio
async def test_search_filters_after_access_checks_without_count_leakage() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "user@example.test")
        # Unfiltered browsing is curator-only; a broad type filter still
        # proves access checks run before filters without leaking counts.
        all_products = await client.get(
            "/api/v1/store/products", params={"productType": "assessment_report"}
        )
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
async def test_store_search_paginates_after_access_and_owner_filters() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "admin@example.test")
        first_page = await client.get(
            "/api/v1/store/products",
            params={"ownerTeam": "RFA", "page": 1, "pageSize": 1},
        )
        second_page = await client.get(
            "/api/v1/store/products",
            params={"ownerTeam": "RFA", "page": 2, "pageSize": 1},
        )
        invalid_page_size = await client.get(
            "/api/v1/store/products",
            params={"page": 1, "pageSize": 0},
        )
        oversized_query = await client.get(
            "/api/v1/store/products",
            params={"query": "x" * 201},
        )

    assert first_page.status_code == 200
    assert first_page.json()["total"] >= 2
    assert first_page.json()["page"] == 1
    assert first_page.json()["pageSize"] == 1
    assert first_page.json()["totalPages"] >= 2
    assert len(first_page.json()["products"]) == 1
    assert len(second_page.json()["products"]) == 1
    assert first_page.json()["products"][0]["id"] != second_page.json()["products"][0]["id"]
    assert all(product["ownerTeam"] == "RFA" for product in first_page.json()["products"])
    assert "assessment_report" in first_page.json()["facets"]["productTypes"]
    assert invalid_page_size.status_code == 422
    assert oversized_query.status_code == 422


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
    assert {"geospatial", "maritime"}.issubset(response.json()["semanticLabels"])


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
