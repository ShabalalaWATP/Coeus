import pytest

from ai_model_helpers import FakeLlmClient, admin_login, make_client


@pytest.mark.asyncio
async def test_admin_reads_state_and_switches_a_provider_model() -> None:
    async with make_client() as client:
        csrf = await admin_login(client)

        state = await client.get("/api/v1/admin/ai-model")
        assert state.status_code == 200
        payload = state.json()
        assert payload["provider"] == "mock"
        assert payload["apiKeyConfigured"] is False
        assert payload["embeddingProvider"] == "mock"
        assert payload["changedBy"] is None
        providers = payload["providers"]
        assert [provider["name"] for provider in providers] == [
            "gemini_api",
            "openai_api",
            "vertex_ai",
            "bedrock",
            "mock",
        ]
        assert providers[0]["label"] == "Gemini API (primary)"
        assert providers[0]["models"] == [
            "gemini-3.5-flash",
            "gemini-3.1-pro-preview",
            "gemma-4-31b-it",
            "gemma-4-26b-a4b-it",
        ]
        assert providers[0]["activeModel"] == "gemini-3.5-flash"
        assert providers[0]["supportsModelRefresh"] is False

        switched = await client.put(
            "/api/v1/admin/ai-model",
            headers={"X-CSRF-Token": csrf},
            json={"model": "gemini-3.1-pro-preview", "provider": "gemini_api"},
        )
        assert switched.status_code == 200
        assert switched.json()["providers"][0]["activeModel"] == "gemini-3.1-pro-preview"
        assert switched.json()["changedBy"] == "admin@example.test"
        assert switched.json()["changedAt"] is not None

        refreshed = await client.get("/api/v1/admin/ai-model")
        assert refreshed.json()["providers"][0]["activeModel"] == "gemini-3.1-pro-preview"


@pytest.mark.asyncio
async def test_key_configuration_stores_the_key_without_switching_provider() -> None:
    async with make_client() as client:
        csrf = await admin_login(client)

        configured = await client.put(
            "/api/v1/admin/ai-model/api-key",
            headers={"X-CSRF-Token": csrf},
            json={"apiKey": "gemini-api-key-value"},
        )
        assert configured.status_code == 200
        assert configured.json()["provider"] == "mock"
        gemini = configured.json()["providers"][0]
        assert gemini["apiKeyConfigured"] is True
        assert "gemini-api-key-value" not in configured.text

        refreshed = await client.get("/api/v1/admin/ai-model")
        assert refreshed.json()["providers"][0]["apiKeyConfigured"] is True
        assert "gemini-api-key-value" not in refreshed.text


@pytest.mark.asyncio
async def test_admin_provider_settings_drive_ticket_assistant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("coeus.integrations.provider_http.httpx.Client", FakeLlmClient)
    FakeLlmClient.captured = {}

    async with make_client() as client:
        csrf = await admin_login(client)
        await client.put(
            "/api/v1/admin/ai-model",
            headers={"X-CSRF-Token": csrf},
            json={"model": "gemini-3.1-pro-preview", "provider": "gemini_api"},
        )
        await client.put(
            "/api/v1/admin/ai-model/api-key",
            headers={"X-CSRF-Token": csrf},
            json={"apiKey": "gemini-api-key-value"},
        )
        await client.put(
            "/api/v1/admin/ai-model/provider",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "gemini_api"},
        )
        user_csrf = await admin_login(client, "user@example.test")
        response = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": user_csrf},
            json={"message": "Need a routine assessment for Baltic ports."},
        )

    assert response.status_code == 201
    assert response.json()["messages"][-1]["body"] == (
        "What specific question should the analysts answer?"
    )
    assert "models/gemini-3.1-pro-preview:generateContent" in str(FakeLlmClient.captured["url"])
    headers = {
        str(key).casefold(): value for key, value in FakeLlmClient.captured["headers"].items()
    }
    assert headers["x-goog-api-key"] == "gemini-api-key-value"


@pytest.mark.asyncio
async def test_env_key_alone_does_not_override_the_configured_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from httpx import ASGITransport, AsyncClient

    from coeus.core.config import Settings
    from coeus.main import create_app

    class ForbiddenClient:
        def __init__(self, *, timeout: int) -> None:
            raise AssertionError("No LLM API may be called when the provider is mock.")

    monkeypatch.setattr("coeus.integrations.provider_http.httpx.Client", ForbiddenClient)
    app = create_app(
        Settings(environment="test", argon2_memory_cost=8_192, gemini_api_key="env-secret")
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await admin_login(client)
        state = await client.get("/api/v1/admin/ai-model")
        assert state.json()["provider"] == "mock"
        assert state.json()["providers"][0]["apiKeyConfigured"] is True

        user_csrf = await admin_login(client, "user@example.test")
        response = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": user_csrf},
            json={"message": "Need a routine assessment for Baltic ports."},
        )

    assert response.status_code == 201
    assert (
        "What is the specific question you would like answered?"
        in response.json()["messages"][-1]["body"]
    )


@pytest.mark.asyncio
async def test_unknown_models_are_rejected() -> None:
    async with make_client() as client:
        csrf = await admin_login(client)

        response = await client.put(
            "/api/v1/admin/ai-model",
            headers={"X-CSRF-Token": csrf},
            json={"model": "gpt-99-ultra", "provider": "gemini_api"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "model_not_available"

        cross_provider = await client.put(
            "/api/v1/admin/ai-model",
            headers={"X-CSRF-Token": csrf},
            json={"model": "gpt-5", "provider": "gemini_api"},
        )
        assert cross_provider.status_code == 422


@pytest.mark.asyncio
async def test_model_selection_requires_admin_permission_and_csrf() -> None:
    async with make_client() as client:
        user_csrf = await admin_login(client, "user@example.test")

        forbidden_read = await client.get("/api/v1/admin/ai-model")
        assert forbidden_read.status_code == 403

        forbidden_write = await client.put(
            "/api/v1/admin/ai-model",
            headers={"X-CSRF-Token": user_csrf},
            json={"model": "gemini-3.1-pro-preview", "provider": "gemini_api"},
        )
        assert forbidden_write.status_code == 403

        forbidden_provider = await client.put(
            "/api/v1/admin/ai-model/provider",
            headers={"X-CSRF-Token": user_csrf},
            json={"provider": "mock"},
        )
        assert forbidden_provider.status_code == 403

        forbidden_test = await client.post(
            "/api/v1/admin/ai-model/test",
            headers={"X-CSRF-Token": user_csrf},
            json={},
        )
        assert forbidden_test.status_code == 403

        await admin_login(client)
        missing_csrf = await client.put(
            "/api/v1/admin/ai-model",
            json={"model": "gemini-3.1-pro-preview", "provider": "gemini_api"},
        )
        assert missing_csrf.status_code == 403
        assert missing_csrf.json()["error"]["code"] == "csrf_failed"
