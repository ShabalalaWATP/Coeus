import json
from hashlib import sha256
from hmac import new as hmac_new
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.main import create_app
from coeus.services.asset_tokens import TOKEN_PREFIX, AssetTokenService, _b64
from store_api_helpers import product_payload

SEED_CREDENTIAL = "CoeusLocal1!"


async def login(client: AsyncClient, username: str) -> dict[str, object]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": SEED_CREDENTIAL},
    )
    assert response.status_code == 200
    return response.json()


def _admin_user(app: object):
    user = app.state.access_services.repository.get_user_by_username("admin@example.test")
    assert user is not None
    return user


@pytest.mark.asyncio
async def test_asset_download_rejects_malformed_tokens(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    product = next(iter(app.state.store_services.repository.list_products()))
    asset = product.assets[0]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "admin@example.test")
        response = await client.get(
            f"/api/v1/store/products/{product.product_id}/assets/{asset.asset_id}/download",
            headers={"X-Asset-Token": "asset-token-not-valid.not-valid"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "asset_token_invalid"


@pytest.mark.asyncio
async def test_asset_download_rechecks_token_claims_and_asset_state(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    product = next(iter(app.state.store_services.repository.list_products()))
    asset = product.assets[0]
    admin = _admin_user(app)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "admin@example.test")
        wrong_product_token = app.state.asset_token_service.issue(admin, uuid4(), asset.asset_id)
        mismatch = await client.get(
            f"/api/v1/store/products/{product.product_id}/assets/{asset.asset_id}/download",
            headers={"X-Asset-Token": wrong_product_token},
        )
        missing_asset_id = uuid4()
        missing_asset_token = app.state.asset_token_service.issue(
            admin, product.product_id, missing_asset_id
        )
        missing_asset = await client.get(
            f"/api/v1/store/products/{product.product_id}/assets/{missing_asset_id}/download",
            headers={"X-Asset-Token": missing_asset_token},
        )
        app.state.object_storage.path_for(asset.object_key).unlink()
        missing_bytes_token = app.state.asset_token_service.issue(
            admin, product.product_id, asset.asset_id
        )
        missing_bytes = await client.get(
            f"/api/v1/store/products/{product.product_id}/assets/{asset.asset_id}/download",
            headers={"X-Asset-Token": missing_bytes_token},
        )

    assert mismatch.status_code == 403
    assert missing_asset.status_code == 404
    assert missing_asset.json()["error"]["code"] == "asset_not_found"
    assert missing_bytes.status_code == 404
    assert missing_bytes.json()["error"]["code"] == "asset_bytes_not_found"


@pytest.mark.asyncio
async def test_break_glass_asset_access_is_audited_and_downloadable(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    content = b"MOCK DATA ONLY break-glass asset bytes"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        created_acg = await client.post(
            "/api/v1/acgs",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={
                "code": "ACG-ASSET-BREAK-GLASS",
                "name": "Asset Break Glass",
                "description": "Synthetic test access group.",
            },
        )
        metadata = product_payload(created_acg.json()["id"])
        metadata.pop("assets")
        created = await client.post(
            "/api/v1/store/products/upload",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            files={
                "asset": ("hidden-brief.txt", content, "text/plain"),
                "metadata": (None, json.dumps(metadata), "application/json"),
            },
        )
        product = created.json()
        asset = product["assets"][0]
        normal_grant = await client.get(
            f"/api/v1/store/products/{product['id']}/assets/{asset['id']}/access"
        )
        reason = "Synthetic support case requiring report-byte validation."
        break_glass_grant = await client.post(
            f"/api/v1/store/products/{product['id']}/assets/{asset['id']}/break-glass-access",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={"reason": reason},
        )
        downloaded = await client.get(
            f"/api/v1/store/products/{product['id']}/assets/{asset['id']}/download",
            headers={"X-Asset-Token": break_glass_grant.json()["downloadToken"]},
        )
        audit = await client.get("/api/v1/audit")

    assert created_acg.status_code == 201
    assert created.status_code == 201
    assert normal_grant.status_code == 404
    assert break_glass_grant.status_code == 200
    assert break_glass_grant.json()["downloadToken"].startswith("asset-token-")
    assert downloaded.status_code == 200
    assert downloaded.content == content
    events = [
        event
        for event in audit.json()["events"]
        if event["eventType"] == "product_asset_break_glass_accessed"
    ]
    assert events[-1]["metadata"]["product_id"] == product["id"]
    assert events[-1]["metadata"]["asset_id"] == asset["id"]
    assert events[-1]["metadata"]["reason"] == reason


@pytest.mark.asyncio
async def test_product_upload_rejects_bad_metadata_and_asset_sizes(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
            local_upload_max_bytes=1,
        )
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        bad_json = await _upload(client, "{bad", b"x", session)
        non_object = await _upload(client, "[]", b"x", session)
        bad_model = await _upload(client, "{}", b"x", session)
        empty = await _upload(client, "{}", b"", session)
        too_large = await _upload(client, "{}", b"xx", session)

    assert bad_json.status_code == 422
    assert non_object.status_code == 422
    assert bad_model.status_code == 422
    assert empty.status_code == 409
    assert too_large.status_code == 413


def test_asset_token_service_rejects_bad_shape_and_expiry() -> None:
    service = AssetTokenService("test-token-secret", ttl_seconds=-1)
    admin = _admin_user(create_app(Settings(environment="test", argon2_memory_cost=8_192)))
    product_id = uuid4()
    asset_id = uuid4()

    with pytest.raises(AppError, match="asset_token_invalid"):
        service.verify("not-a-token")
    with pytest.raises(AppError, match="asset_token_invalid"):
        service.verify(_signed_bad_payload(service))
    with pytest.raises(AppError, match="asset_token_expired"):
        service.verify(service.issue(admin, product_id, asset_id))


async def _upload(
    client: AsyncClient,
    metadata: str,
    content: bytes,
    session: dict[str, object] | None = None,
):
    csrf_token = str((session or await login(client, "admin@example.test"))["csrfToken"])
    return await client.post(
        "/api/v1/store/products/upload",
        headers={"X-CSRF-Token": csrf_token},
        files={
            "asset": ("asset", content, "application/octet-stream"),
            "metadata": (None, metadata, "application/json"),
        },
    )


def _signed_bad_payload(service: AssetTokenService) -> str:
    encoded = _b64(b"not-json")
    signature = _b64(hmac_new(service._secret, encoded.encode("ascii"), sha256).digest())
    return f"{TOKEN_PREFIX}{encoded}.{signature}"
