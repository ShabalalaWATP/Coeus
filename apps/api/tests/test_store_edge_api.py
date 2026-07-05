from dataclasses import replace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.access import ProductStatus
from coeus.domain.auth import UserAccount
from coeus.domain.store import StoreSearchFilters
from coeus.main import create_app

SEED_CREDENTIAL = "CoeusLocal1!"


async def login(client: AsyncClient, username: str) -> dict[str, object]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": SEED_CREDENTIAL},
    )
    assert response.status_code == 200
    return response.json()


def product_payload(acg_id: str) -> dict[str, object]:
    return {
        "title": "Mock Harbour Activity Brief",
        "summary": "MOCK DATA ONLY assessment of harbour activity.",
        "description": "Synthetic product metadata for Sprint 5 testing.",
        "productType": "assessment_report",
        "sourceType": "finished_assessment",
        "ownerTeam": "RFA",
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
async def test_store_routes_validate_preview_status_and_basic_permissions() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    acg_id = str(app.state.access_services.repository.list_acgs()[0].acg_id)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        customer_session = await login(client, "user@example.test")
        forbidden_create = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(customer_session["csrfToken"])},
            json=product_payload(acg_id),
        )
        admin_session = await login(client, "admin@example.test")
        preview = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(admin_session["csrfToken"])},
            json={**product_payload(acg_id), "assets": preview_assets()},
        )
        bad_status = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(admin_session["csrfToken"])},
            json={**product_payload(acg_id), "status": "retired"},
        )
        bad_size = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(admin_session["csrfToken"])},
            json={**product_payload(acg_id), "assets": [sized_asset(0)]},
        )
        suggestion = await client.post(
            "/api/v1/store/metadata-suggestions",
            headers={"X-CSRF-Token": str(admin_session["csrfToken"])},
            json={
                "title": "Mock Vessel Report",
                "summary": "MOCK DATA ONLY report for North Sea activity.",
                "productType": "assessment_report",
                "areaOrRegion": "North Sea",
            },
        )

    assert forbidden_create.status_code == 403
    assert preview.status_code == 201
    assert [asset["previewKind"] for asset in preview.json()["assets"]] == [
        "image",
        "geojson",
        "text_metadata",
    ]
    assert bad_status.json()["error"]["code"] == "product_status_invalid"
    assert bad_size.json()["error"]["code"] == "asset_size_invalid"
    assert suggestion.json()["tags"] == ["mock"]


@pytest.mark.asyncio
async def test_inactive_acg_rejects_product_creation() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    acg = app.state.access_services.repository.list_acgs()[0]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        await client.patch(
            f"/api/v1/acgs/{acg.acg_id}",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={"isActive": False},
        )
        response = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json=product_payload(str(acg.acg_id)),
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "product_acg_required"


def test_store_services_cover_restricted_policy_branches() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    services = app.state.store_services
    regional = next(
        product
        for product in services.repository.list_products()
        if product.metadata.title == "Regional Stability Brief"
    )
    customer = app.state.access_services.repository.get_user_by_username("user@example.test")
    assert customer is not None
    no_permissions = UserAccount(
        user_id=uuid4(),
        username="none@example.test",
        display_name="No Permissions",
        roles=frozenset(),
        permissions=frozenset(),
        password_hash="",
        is_active=True,
        clearance_level=3,
    )
    archived = replace(
        regional,
        metadata=replace(regional.metadata, status=ProductStatus.ARCHIVED),
    )
    services.repository.save_product(archived)

    with pytest.raises(AppError, match="forbidden"):
        services.search.search(no_permissions, StoreSearchFilters())
    with pytest.raises(AppError, match="forbidden"):
        services.assets.grant_access(
            replace(customer, permissions=frozenset({Permission.PRODUCT_READ})),
            regional.product_id,
            regional.assets[0].asset_id,
        )
    with pytest.raises(AppError, match="product_not_found"):
        services.details.get_visible_product(
            replace(customer, is_active=False), regional.product_id
        )
    with pytest.raises(AppError, match="product_not_found"):
        services.details.get_visible_product(
            replace(customer, clearance_level=1),
            regional.product_id,
        )
    with pytest.raises(AppError, match="product_not_found"):
        services.details.get_visible_product(customer, archived.product_id)


def preview_assets() -> list[dict[str, object]]:
    return [
        sized_asset(42, name="mock-image.png", asset_type="image", mime_type="image/png", char="c"),
        sized_asset(
            42,
            name="mock-layer.geojson",
            asset_type="geojson",
            mime_type="application/geo+json",
            char="d",
        ),
        sized_asset(
            42,
            name="mock-note.txt",
            asset_type="text",
            mime_type="text/plain",
            char="e",
        ),
    ]


def sized_asset(
    size_bytes: int,
    *,
    name: str = "empty.pdf",
    asset_type: str = "pdf",
    mime_type: str = "application/pdf",
    char: str = "f",
) -> dict[str, object]:
    return {
        "name": name,
        "assetType": asset_type,
        "mimeType": mime_type,
        "sizeBytes": size_bytes,
        "sha256": char * 64,
    }
