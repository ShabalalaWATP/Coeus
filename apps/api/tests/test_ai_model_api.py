import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app

SEED_CREDENTIAL = "CoeusLocal1!"


def _client() -> AsyncClient:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _login(client: AsyncClient, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": SEED_CREDENTIAL},
    )
    assert response.status_code == 200
    return str(response.json()["csrfToken"])


@pytest.mark.asyncio
async def test_admin_reads_and_switches_the_active_gemini_model() -> None:
    async with _client() as client:
        csrf = await _login(client, "admin@example.test")

        state = await client.get("/api/v1/admin/ai-model")
        assert state.status_code == 200
        payload = state.json()
        assert payload["provider"] == "mock"
        assert payload["activeModel"] == "gemma-4-31b"
        assert "gemini-2.5-pro" in payload["availableModels"]
        assert payload["changedBy"] is None
        assert payload["changedAt"] is None

        switched = await client.put(
            "/api/v1/admin/ai-model",
            headers={"X-CSRF-Token": csrf},
            json={"model": "gemini-2.5-pro"},
        )
        assert switched.status_code == 200
        assert switched.json()["activeModel"] == "gemini-2.5-pro"
        assert switched.json()["changedBy"] == "admin@example.test"
        assert switched.json()["changedAt"] is not None

        refreshed = await client.get("/api/v1/admin/ai-model")
        assert refreshed.json()["activeModel"] == "gemini-2.5-pro"
        assert refreshed.json()["changedBy"] == "admin@example.test"


@pytest.mark.asyncio
async def test_unknown_models_are_rejected() -> None:
    async with _client() as client:
        csrf = await _login(client, "admin@example.test")

        response = await client.put(
            "/api/v1/admin/ai-model",
            headers={"X-CSRF-Token": csrf},
            json={"model": "gpt-99-ultra"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "model_not_available"


@pytest.mark.asyncio
async def test_model_selection_requires_admin_permission_and_csrf() -> None:
    async with _client() as client:
        user_csrf = await _login(client, "user@example.test")

        forbidden_read = await client.get("/api/v1/admin/ai-model")
        assert forbidden_read.status_code == 403

        forbidden_write = await client.put(
            "/api/v1/admin/ai-model",
            headers={"X-CSRF-Token": user_csrf},
            json={"model": "gemini-2.5-pro"},
        )
        assert forbidden_write.status_code == 403

        await _login(client, "admin@example.test")
        missing_csrf = await client.put(
            "/api/v1/admin/ai-model",
            json={"model": "gemini-2.5-pro"},
        )
        assert missing_csrf.status_code == 403
        assert missing_csrf.json()["error"]["code"] == "csrf_failed"
