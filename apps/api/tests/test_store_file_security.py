import json
from pathlib import Path
from typing import Any, cast

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.auth import RoleName
from coeus.main import create_app
from coeus.services.product_processing import process_product_file
from store_api_helpers import product_payload

SEED_CREDENTIAL = "CoeusLocal1!"
PNG_BYTES = b"\x89PNG\r\n\x1a\nMOCK DATA ONLY admitted image"
MALWARE_MARKER = b"EICAR-STANDARD-" + b"ANTIVIRUS-TEST-FILE"


async def _login(client: AsyncClient, username: str) -> dict[str, object]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": SEED_CREDENTIAL},
    )
    assert response.status_code == 200
    return cast(dict[str, object], response.json())


def _upload_metadata(app: Any) -> str:
    acg_id = str(app.state.access_services.repository.list_acgs()[0].acg_id)
    metadata = product_payload(acg_id)
    metadata.pop("assets")
    return json.dumps(metadata)


async def _upload(
    client: AsyncClient,
    csrf_token: object,
    metadata: str,
    filename: str,
    content: bytes,
    declared_mime: str,
):
    return await client.post(
        "/api/v1/store/products/upload",
        headers={"X-CSRF-Token": str(csrf_token)},
        files={
            "asset": (filename, content, declared_mime),
            "metadata": (None, metadata, "application/json"),
        },
    )


@pytest.mark.asyncio
async def test_stale_normal_asset_token_cannot_download_or_preview(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    product = next(
        item
        for item in app.state.store_services.repository.list_products()
        if item.reference == "PROD-1001"
    )
    asset = product.assets[0]
    app.state.object_storage.write_bytes(asset.object_key, PNG_BYTES)

    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as admin,
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as user,
    ):
        admin_session = await _login(admin, "admin@example.test")
        users = await admin.get("/api/v1/admin/users")
        target = next(
            cast(dict[str, Any], item)
            for item in users.json()["users"]
            if item["username"] == "user@example.test"
        )
        user_id = target["id"]
        clearance = await admin.put(
            f"/api/v1/admin/users/{user_id}/clearance",
            headers={"X-CSRF-Token": str(admin_session["csrfToken"])},
            json={"clearanceLevel": 4},
        )
        assert clearance.status_code == 200
        promoted = await admin.put(
            f"/api/v1/admin/users/{user_id}/roles",
            headers={"X-CSRF-Token": str(admin_session["csrfToken"])},
            json={"roles": ["Intelligence Store Manager"]},
        )
        assert promoted.status_code == 200

        await _login(user, "user@example.test")
        asset_base = f"/api/v1/store/products/{product.product_id}/assets/{asset.asset_id}"
        grant = await user.get(f"{asset_base}/access")
        assert grant.status_code == 200
        retained_token = grant.json()["downloadToken"]

        downgraded = await admin.put(
            f"/api/v1/admin/users/{user_id}/roles",
            headers={"X-CSRF-Token": str(admin_session["csrfToken"])},
            json={"roles": ["Analyst"]},
        )
        assert downgraded.status_code == 200
        assert (await user.get("/api/v1/auth/me")).status_code == 401
        await _login(user, "user@example.test")

        assert (await user.get(f"{asset_base}/access")).status_code == 403
        headers = {"X-Asset-Token": retained_token}
        download = await user.get(f"{asset_base}/download", headers=headers)
        preview = await user.get(f"{asset_base}/preview", headers=headers)

    assert download.status_code == 403
    assert download.json()["error"]["code"] == "forbidden"
    assert preview.status_code == 403
    assert preview.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_store_upload_rejects_malware_before_persistence(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    before = len(app.state.store_services.repository.list_products())
    content = PNG_BYTES + MALWARE_MARKER

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await _login(client, "store.manager@example.test")
        response = await _upload(
            client,
            session["csrfToken"],
            _upload_metadata(app),
            "blocked.png",
            content,
            "image/png",
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "malware_detected"
    assert len(app.state.store_services.repository.list_products()) == before
    assert not list((tmp_path / "objects").rglob("*"))


@pytest.mark.asyncio
async def test_store_upload_uses_content_derived_metadata_and_preserves_bytes(
    tmp_path: Path,
) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await _login(client, "admin@example.test")
        response = await _upload(
            client,
            session["csrfToken"],
            _upload_metadata(app),
            "admitted.png",
            PNG_BYTES,
            "application/octet-stream",
        )
        assert response.status_code == 201, response.text
        product = response.json()
        asset = product["assets"][0]
        grant = await client.get(
            f"/api/v1/store/products/{product['id']}/assets/{asset['id']}/access"
        )
        downloaded = await client.get(
            f"/api/v1/store/products/{product['id']}/assets/{asset['id']}/download",
            headers={"X-Asset-Token": grant.json()["downloadToken"]},
        )

    assert asset["mimeType"] == "image/png"
    assert asset["assetType"] == "png"
    assert asset["previewKind"] == "image"
    assert downloaded.status_code == 200
    assert downloaded.content == PNG_BYTES


@pytest.mark.parametrize(
    ("authority_change", "status"),
    [
        ("remove_create", "draft"),
        ("remove_publish", "published"),
        ("disable", "draft"),
    ],
)
@pytest.mark.asyncio
async def test_store_upload_rechecks_current_authority_at_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_change: str,
    status: str,
) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    access = app.state.access_services.repository
    actor = access.get_user_by_username("store.manager@example.test")
    admin = access.get_user_by_username("admin@example.test")
    assert actor is not None
    assert admin is not None
    metadata = json.loads(_upload_metadata(app))
    metadata.update(
        {
            "title": f"Mock rejected stale authority {authority_change}",
            "status": status,
        }
    )
    before = len(app.state.store_services.repository.list_products())
    staged_paths: list[Path] = []

    def change_authority_during_processing(*args: Any, **kwargs: Any):
        staged_paths.append(cast(Path, args[0]))
        if authority_change == "remove_create":
            app.state.user_admin_service.set_roles(
                admin,
                actor.user_id,
                frozenset({RoleName.INTELLIGENCE_ANALYST}),
            )
        elif authority_change == "remove_publish":
            app.state.user_admin_service.set_roles(
                admin,
                actor.user_id,
                frozenset({RoleName.RFA_MANAGER}),
            )
        else:
            app.state.user_admin_service.set_active(admin, actor.user_id, False)
        return process_product_file(*args, **kwargs)

    monkeypatch.setattr(
        "coeus.api.routes.store_files.process_product_file",
        change_authority_during_processing,
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await _login(client, actor.username)
        response = await _upload(
            client,
            session["csrfToken"],
            json.dumps(metadata),
            "authority-race.png",
            PNG_BYTES,
            "image/png",
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert len(app.state.store_services.repository.list_products()) == before
    assert not list((tmp_path / "objects").rglob("*"))
    assert staged_paths and all(not path.exists() for path in staged_paths)
