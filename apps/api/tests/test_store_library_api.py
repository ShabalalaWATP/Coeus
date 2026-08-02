from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.main import create_app
from coeus.persistence.state_store import MemoryStateStore
from coeus.services.audit import AuditLog
from coeus.services.store_library import StoreLibraryService
from store_api_helpers import login


async def _visible_product_id(client: AsyncClient) -> str:
    response = await client.get(
        "/api/v1/store/products", params={"productType": "assessment_report"}
    )
    assert response.status_code == 200
    return str(response.json()["products"][0]["id"])


@pytest.mark.asyncio
async def test_personal_library_folder_and_product_lifecycle() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "user@example.test")
        csrf = str(session["csrfToken"])
        product_id = await _visible_product_id(client)

        folder_response = await client.post(
            "/api/v1/store/library/folders",
            headers={"X-CSRF-Token": csrf},
            json={"name": "  Eastern Europe  "},
        )
        assert folder_response.status_code == 201
        folder = folder_response.json()
        assert folder["name"] == "Eastern Europe"

        saved_response = await client.put(
            f"/api/v1/store/library/products/{product_id}",
            headers={"X-CSRF-Token": csrf},
            json={"folderId": folder["id"]},
        )
        assert saved_response.status_code == 200
        assert saved_response.json()["folderId"] == folder["id"]

        library = (await client.get("/api/v1/store/library")).json()
        assert library["folders"] == [folder]
        assert library["savedProducts"][0]["product"]["id"] == product_id
        assert library["unavailableCount"] == 0

        deleted_folder = await client.delete(
            f"/api/v1/store/library/folders/{folder['id']}",
            headers={"X-CSRF-Token": csrf},
        )
        assert deleted_folder.status_code == 204
        assert (await client.get("/api/v1/store/library")).json()["savedProducts"][0][
            "folderId"
        ] is None

        removed = await client.delete(
            f"/api/v1/store/library/products/{product_id}",
            headers={"X-CSRF-Token": csrf},
        )
        assert removed.status_code == 204
        assert (await client.get("/api/v1/store/library")).json()["savedProducts"] == []


@pytest.mark.asyncio
async def test_library_rejects_cross_user_folder_and_missing_csrf() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://testserver") as owner,
        AsyncClient(transport=transport, base_url="http://testserver") as other,
    ):
        owner_session = await login(owner, "user@example.test")
        folder_response = await owner.post(
            "/api/v1/store/library/folders",
            headers={"X-CSRF-Token": str(owner_session["csrfToken"])},
            json={"name": "Personal"},
        )
        folder_id = folder_response.json()["id"]
        other_session = await login(other, "admin@example.test")
        product_id = await _visible_product_id(other)

        missing_csrf = await other.post("/api/v1/store/library/folders", json={"name": "No token"})
        cross_user = await other.put(
            f"/api/v1/store/library/products/{product_id}",
            headers={"X-CSRF-Token": str(other_session["csrfToken"])},
            json={"folderId": folder_id},
        )

        assert missing_csrf.status_code == 403
        assert cross_user.status_code == 404
        assert (await other.get("/api/v1/store/library")).json()["folders"] == []


@pytest.mark.asyncio
async def test_library_rejects_duplicate_folder_names() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "user@example.test")
        headers = {"X-CSRF-Token": str(session["csrfToken"])}
        first = await client.post(
            "/api/v1/store/library/folders", headers=headers, json={"name": "Watchlist"}
        )
        duplicate = await client.post(
            "/api/v1/store/library/folders", headers=headers, json={"name": "watchlist"}
        )

        assert first.status_code == 201
        assert duplicate.status_code == 409
        whitespace = await client.post(
            "/api/v1/store/library/folders", headers=headers, json={"name": "   "}
        )
        assert whitespace.status_code == 422


@pytest.mark.asyncio
async def test_library_omits_products_that_are_no_longer_visible() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "user@example.test")
        visible_id = await _visible_product_id(client)
        hidden_product = next(
            product
            for product in app.state.store_services.repository.list_products()
            if str(product.product_id) != visible_id
        )
        app.state.store_services.library.save_product(
            UUID(str(session["user"]["id"])), hidden_product.product_id, None
        )

        library = (await client.get("/api/v1/store/library")).json()

        assert library["savedProducts"] == []
        assert library["unavailableCount"] == 1


def test_library_service_enforces_limits_and_missing_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import coeus.services.store_library as library_module

    monkeypatch.setattr(library_module, "MAX_FOLDERS_PER_USER", 1)
    monkeypatch.setattr(library_module, "MAX_SAVED_PRODUCTS_PER_USER", 1)
    service = StoreLibraryService(MemoryStateStore(), AuditLog())
    user_id = uuid4()
    folder = service.create_folder(user_id, "Watchlist")

    with pytest.raises(AppError) as folder_error:
        service.create_folder(user_id, "Second")
    assert folder_error.value.code == "folder_limit_reached"

    product_id = uuid4()
    first = service.save_product(user_id, product_id, folder.folder_id)
    moved = service.save_product(user_id, product_id, None)
    assert moved.saved_at == first.saved_at
    assert moved.folder_id is None

    with pytest.raises(AppError) as product_error:
        service.save_product(user_id, uuid4(), None)
    assert product_error.value.code == "saved_product_limit_reached"

    service.remove_product(user_id, product_id)
    with pytest.raises(AppError) as missing_error:
        service.remove_product(user_id, product_id)
    assert missing_error.value.code == "saved_product_not_found"


def test_library_service_rolls_back_when_audit_persistence_fails() -> None:
    state_store = MemoryStateStore()
    audit_log = Mock(spec=AuditLog)
    audit_log.record.side_effect = RuntimeError("audit unavailable")
    service = StoreLibraryService(state_store, audit_log)

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.create_folder(uuid4(), "Watchlist")

    assert state_store.load("store_personal_libraries") == {
        "folders": [],
        "savedProducts": [],
    }
