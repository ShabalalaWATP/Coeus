import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from store_api_helpers import login, product_payload


@pytest.mark.asyncio
async def test_product_creation_persistence_failure_rolls_back_product(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    acg_id = str(app.state.access_services.repository.list_acgs()[0].acg_id)

    def fail_persist() -> None:
        raise RuntimeError("simulated store persistence failure")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        monkeypatch.setattr(app.state.store_services.repository, "_persist", fail_persist)
        with pytest.raises(RuntimeError, match="simulated store persistence failure"):
            await client.post(
                "/api/v1/store/products",
                headers={"X-CSRF-Token": str(session["csrfToken"])},
                json=product_payload(acg_id),
            )

    assert all(
        product.metadata.title != "Mock Harbour Activity Brief"
        for product in app.state.store_services.repository.list_products()
    )


@pytest.mark.asyncio
async def test_product_creation_audit_failure_rolls_back_product(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    acg_id = str(app.state.access_services.repository.list_acgs()[0].acg_id)
    before_count = len(app.state.store_services.repository.list_products())

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        monkeypatch.setattr(app.state.store_services.ingestion._audit_log, "record", _fail_audit)
        with pytest.raises(RuntimeError, match="audit unavailable"):
            await client.post(
                "/api/v1/store/products",
                headers={"X-CSRF-Token": str(session["csrfToken"])},
                json=product_payload(acg_id),
            )

    products = app.state.store_services.repository.list_products()
    assert len(products) == before_count
    assert all(product.metadata.title != "Mock Harbour Activity Brief" for product in products)


def _fail_audit(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("audit unavailable")
