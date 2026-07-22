import pytest
from httpx import ASGITransport, AsyncClient

from ai_model_helpers import SEED_CREDENTIAL
from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import product_payload, submitted_ticket


async def _login(client: AsyncClient, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": SEED_CREDENTIAL},
    )
    assert response.status_code == 200
    return str(response.json()["csrfToken"])


@pytest.mark.asyncio
async def test_admin_configures_search_key_without_changing_chat_key() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        csrf = await _login(client, "admin@example.test")
        initial = await client.get("/api/v1/admin/search-embeddings")
        configured = await client.put(
            "/api/v1/admin/search-embeddings/api-key",
            headers={"X-CSRF-Token": csrf},
            json={"apiKey": "search-only-secret-value"},
        )
        chat = await client.get("/api/v1/admin/ai-model")

    assert initial.status_code == 200
    assert initial.json()["model"] == "token-hash-v2"
    assert initial.json()["dimensions"] == 1536
    assert configured.status_code == 200
    assert configured.json()["apiKeyConfigured"] is True
    assert "search-only-secret-value" not in configured.text
    assert chat.json()["providers"][0]["apiKeyConfigured"] is False


@pytest.mark.asyncio
async def test_admin_selects_recommended_model_tests_and_reindexes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, *_args: object, **_kwargs: object):
            return self

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"embedding": {"values": [1.0] * 1536}}

    monkeypatch.setattr(
        "coeus.services.search_embeddings.httpx.Client", lambda **_kwargs: FakeClient()
    )
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        csrf = await _login(client, "admin@example.test")
        await client.put(
            "/api/v1/admin/search-embeddings/api-key",
            headers={"X-CSRF-Token": csrf},
            json={"apiKey": "search-only-secret-value"},
        )
        denied = await client.put(
            "/api/v1/admin/search-embeddings/configuration",
            headers={"X-CSRF-Token": csrf},
            json={
                "provider": "gemini_api",
                "model": "gemini-embedding-2",
                "confirmExternalEgress": False,
            },
        )
        selected = await client.put(
            "/api/v1/admin/search-embeddings/configuration",
            headers={"X-CSRF-Token": csrf},
            json={
                "provider": "gemini_api",
                "model": "gemini-embedding-2",
                "confirmExternalEgress": True,
            },
        )
        tested = await client.post(
            "/api/v1/admin/search-embeddings/test",
            headers={"X-CSRF-Token": csrf},
        )

    assert denied.status_code == 422
    assert selected.status_code == 200
    assert selected.json()["model"] == "gemini-embedding-2"
    assert selected.json()["indexStatus"] == "stale"
    assert tested.status_code == 200
    assert tested.json()["ok"] is True


@pytest.mark.asyncio
async def test_mock_reindex_runs_as_a_generation_aware_background_job() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        csrf = await _login(client, "admin@example.test")
        first = await client.post(
            "/api/v1/admin/search-embeddings/reindex",
            headers={"X-CSRF-Token": csrf},
        )
        ready = await client.get("/api/v1/admin/search-embeddings")
        second = await client.post(
            "/api/v1/admin/search-embeddings/reindex",
            headers={"X-CSRF-Token": csrf},
        )
        ready_again = await client.get("/api/v1/admin/search-embeddings")

    assert first.status_code == 202
    assert ready.json()["indexStatus"] == "ready"
    assert ready.json()["chunkCount"] >= ready.json()["productCount"]
    assert second.status_code == 202
    assert ready_again.json()["indexStatus"] == "ready"
    assert ready_again.json()["indexGeneration"] == ready.json()["indexGeneration"] + 1


@pytest.mark.asyncio
async def test_non_admin_cannot_read_search_configuration() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await _login(client, "user@example.test")
        response = await client.get("/api/v1/admin/search-embeddings")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_reindex_reports_missing_or_unsupported_asset_warnings() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    regional_acg = next(
        acg for acg in app.state.access_services.repository.list_acgs() if "ALPHA" in acg.code
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        csrf = await _login(client, "admin@example.test")
        created = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": csrf},
            json=product_payload(
                str(regional_acg.acg_id),
                title="Synthetic product with missing search asset",
            ),
        )
        reindexed = await client.post(
            "/api/v1/admin/search-embeddings/reindex",
            headers={"X-CSRF-Token": csrf},
        )
        state = await client.get("/api/v1/admin/search-embeddings")

    assert created.status_code == 201
    assert reindexed.status_code == 202
    assert state.json()["failedAssetCount"] >= 1
    assert state.json()["ticketCount"] >= 0


@pytest.mark.asyncio
async def test_new_active_request_does_not_invalidate_the_product_corpus() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        admin_csrf = await _login(client, "admin@example.test")
        reindexed = await client.post(
            "/api/v1/admin/search-embeddings/reindex",
            headers={"X-CSRF-Token": admin_csrf},
        )
        ready = await client.get("/api/v1/admin/search-embeddings")
        user_csrf = await _login(client, "user@example.test")
        await submitted_ticket(client, user_csrf, title="New corpus requirement")
        await _login(client, "admin@example.test")
        stale = await client.get("/api/v1/admin/search-embeddings")

    assert reindexed.status_code == 202
    assert ready.json()["indexStatus"] == "ready"
    assert stale.json()["indexStatus"] == "ready"
    assert stale.json()["degradedReason"] is None
