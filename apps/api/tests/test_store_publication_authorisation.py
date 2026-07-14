import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from store_api_helpers import login, product_payload


@pytest.mark.asyncio
async def test_product_creator_cannot_publish_without_release_authority() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    access = app.state.access_services.repository
    actor = access.get_user_by_username("rfa.manager@example.test")
    assert actor is not None
    rfa_acg = next(
        acg
        for acg in access.list_acgs()
        if acg.acg_id in access.active_acg_ids_for_user(actor.user_id)
    )
    payload = {
        **product_payload(str(rfa_acg.acg_id)),
        "title": "Mock Release Boundary Product",
        "status": "published",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, actor.username)
        denied = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json=payload,
        )
        allowed_draft = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={**payload, "status": "draft"},
        )
        omitted_status = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={key: value for key, value in payload.items() if key != "status"}
            | {"title": "Mock Default Draft Product"},
        )
        archived = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={**payload, "title": "Mock Invalid Archived Product", "status": "archived"},
        )
        admin = await login(client, "admin@example.test")
        authorised = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
            json={**payload, "title": "Mock Authorised Published Product"},
        )

    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "forbidden"
    assert allowed_draft.status_code == 201
    assert allowed_draft.json()["status"] == "draft"
    assert omitted_status.status_code == 201
    assert omitted_status.json()["status"] == "draft"
    assert archived.status_code == 409
    assert archived.json()["error"]["code"] == "product_status_invalid"
    assert authorised.status_code == 201
    assert authorised.json()["status"] == "published"
    matching = [
        product
        for product in app.state.store_services.repository.list_products()
        if product.metadata.title == payload["title"]
    ]
    assert [product.metadata.status.value for product in matching] == ["draft"]


@pytest.mark.asyncio
async def test_multipart_upload_cannot_bypass_publication_authority(tmp_path: Path) -> None:
    object_root = tmp_path / "objects"
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(object_root),
        )
    )
    access = app.state.access_services.repository
    actor = access.get_user_by_username("rfa.manager@example.test")
    assert actor is not None
    acg_id = next(iter(access.active_acg_ids_for_user(actor.user_id)))
    metadata = product_payload(str(acg_id))
    metadata.pop("assets")
    metadata.update({"title": "Mock Multipart Release Bypass", "status": "published"})

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, actor.username)
        denied = await client.post(
            "/api/v1/store/products/upload",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            files={
                "asset": ("mock.txt", b"MOCK DATA ONLY", "text/plain"),
                "metadata": (None, json.dumps(metadata), "application/json"),
            },
        )

    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "forbidden"
    assert not any(
        product.metadata.title == metadata["title"]
        for product in app.state.store_services.repository.list_products()
    )
    assert not object_root.exists() or not any(object_root.rglob("*"))
