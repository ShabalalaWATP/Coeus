import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from coeus.services.object_storage import LocalObjectStorage
from store_api_helpers import login, product_payload


class FailingObjectStorage(LocalObjectStorage):
    def write_bytes(self, object_key: str, content: bytes) -> None:
        super().write_bytes(object_key, b"partial")
        raise OSError("synthetic storage failure")


@pytest.mark.asyncio
async def test_upload_rolls_back_product_when_asset_storage_fails(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    app.state.object_storage = FailingObjectStorage(tmp_path / "failing-objects")
    acg_id = str(app.state.access_services.repository.list_acgs()[0].acg_id)
    metadata = product_payload(acg_id)
    metadata.pop("assets")
    before_count = len(app.state.store_services.repository.list_products())

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        response = await client.post(
            "/api/v1/store/products/upload",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            files={
                "asset": ("uploaded-brief.txt", b"MOCK DATA ONLY", "text/plain"),
                "metadata": (None, json.dumps(metadata), "application/json"),
            },
        )

    products = app.state.store_services.repository.list_products()
    audit_types = [event.event_type for event in app.state.auth_service.audit_log.list_events()]
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "asset_storage_failed"
    assert len(products) == before_count
    assert all(product.metadata.title != "Mock Harbour Activity Brief" for product in products)
    assert "product_created" not in audit_types
    assert not any((tmp_path / "failing-objects").rglob("*"))


@pytest.mark.asyncio
async def test_upload_rolls_back_product_and_bytes_when_audit_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    object_root = tmp_path / "objects"
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(object_root),
        )
    )
    acg_id = str(app.state.access_services.repository.list_acgs()[0].acg_id)
    metadata = product_payload(acg_id)
    metadata.pop("assets")
    before_count = len(app.state.store_services.repository.list_products())

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        monkeypatch.setattr(app.state.store_services.ingestion._audit_log, "record", _fail_audit)
        with pytest.raises(RuntimeError, match="audit unavailable"):
            await client.post(
                "/api/v1/store/products/upload",
                headers={"X-CSRF-Token": str(session["csrfToken"])},
                files={
                    "asset": ("uploaded-brief.txt", b"MOCK DATA ONLY", "text/plain"),
                    "metadata": (None, json.dumps(metadata), "application/json"),
                },
            )

    products = app.state.store_services.repository.list_products()
    assert len(products) == before_count
    assert all(product.metadata.title != "Mock Harbour Activity Brief" for product in products)
    assert not any(path.name == "uploaded-brief.txt" for path in object_root.rglob("*"))


def _fail_audit(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("audit unavailable")
