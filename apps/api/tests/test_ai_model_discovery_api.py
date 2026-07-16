"""Refreshing models from a provider and adding models by hand."""

import inspect

import pytest

from ai_model_helpers import admin_login, make_client
from coeus.api.routes.admin import (
    refresh_ai_models as refresh_route,
)
from coeus.api.routes.admin import (
    test_ai_connection as connection_test_route,
)


def test_synchronous_provider_routes_are_offloaded_by_fastapi() -> None:
    assert not inspect.iscoroutinefunction(refresh_route)
    assert not inspect.iscoroutinefunction(connection_test_route)


@pytest.mark.asyncio
async def test_openai_catalogue_is_curated_and_cannot_be_refreshed() -> None:
    async with make_client() as client:
        csrf = await admin_login(client)
        await client.put(
            "/api/v1/admin/ai-model/api-key",
            headers={"X-CSRF-Token": csrf},
            json={"apiKey": "sk-openai-key-value", "provider": "openai_api"},
        )

        refreshed = await client.post(
            "/api/v1/admin/ai-model/refresh",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "openai_api"},
        )
        assert refreshed.status_code == 422
        assert refreshed.json()["error"]["code"] == "refresh_not_supported"
        state = await client.get("/api/v1/admin/ai-model")
        openai = next(p for p in state.json()["providers"] if p["name"] == "openai_api")
        assert openai["models"] == ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"]
        assert openai["supportsModelRefresh"] is False


@pytest.mark.asyncio
async def test_refresh_requires_a_key_and_supported_provider() -> None:
    async with make_client() as client:
        csrf = await admin_login(client)

        keyless = await client.post(
            "/api/v1/admin/ai-model/refresh",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "openai_api"},
        )
        assert keyless.status_code == 422
        assert keyless.json()["error"]["code"] == "refresh_not_supported"

        unsupported = await client.post(
            "/api/v1/admin/ai-model/refresh",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "vertex_ai"},
        )
        assert unsupported.status_code == 422
        assert unsupported.json()["error"]["code"] == "refresh_not_supported"

        curated = await client.post(
            "/api/v1/admin/ai-model/refresh",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "gemini_api"},
        )
        assert curated.status_code == 422
        assert curated.json()["error"]["code"] == "refresh_not_supported"

        state = await client.get("/api/v1/admin/ai-model")
        vertex = next(p for p in state.json()["providers"] if p["name"] == "vertex_ai")
        assert vertex["supportsModelRefresh"] is False


@pytest.mark.asyncio
async def test_admin_adds_a_custom_model_without_activating_it() -> None:
    async with make_client() as client:
        csrf = await admin_login(client)

        added = await client.post(
            "/api/v1/admin/ai-model/custom-model",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "bedrock", "model": "anthropic.claude-opus-5-20261101-v1:0"},
        )
        assert added.status_code == 200
        bedrock = next(p for p in added.json()["providers"] if p["name"] == "bedrock")
        assert "anthropic.claude-opus-5-20261101-v1:0" in bedrock["models"]
        original_model = "anthropic.claude-sonnet-4-5-20250929-v1:0"
        assert bedrock["activeModel"] == original_model

        # Adding the same ID again is an idempotent no-op.
        again = await client.post(
            "/api/v1/admin/ai-model/custom-model",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "bedrock", "model": "anthropic.claude-opus-5-20261101-v1:0"},
        )
        assert again.status_code == 200
        repeated = next(p for p in again.json()["providers"] if p["name"] == "bedrock")
        assert repeated["activeModel"] == original_model

        selected = await client.put(
            "/api/v1/admin/ai-model",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "bedrock", "model": "anthropic.claude-opus-5-20261101-v1:0"},
        )
        assert selected.status_code == 200

        rejected = await client.post(
            "/api/v1/admin/ai-model/custom-model",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "mock", "model": "whatever"},
        )
        assert rejected.status_code == 422

        bad_id = await client.post(
            "/api/v1/admin/ai-model/custom-model",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "openai_api", "model": "bad id with spaces"},
        )
        assert bad_id.status_code == 422
        assert "Model IDs may contain only" in bad_id.json()["detail"][0]["msg"]

        curated = await client.post(
            "/api/v1/admin/ai-model/custom-model",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "gemini_api", "model": "gemini-2.5-pro"},
        )
        assert curated.status_code == 422
        assert curated.json()["error"]["code"] == "model_catalogue_curated"

        openai_curated = await client.post(
            "/api/v1/admin/ai-model/custom-model",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "openai_api", "model": "gpt-5"},
        )
        assert openai_curated.status_code == 422
        assert openai_curated.json()["error"]["code"] == "model_catalogue_curated"


@pytest.mark.asyncio
async def test_refresh_and_custom_require_admin_and_csrf() -> None:
    async with make_client() as client:
        user_csrf = await admin_login(client, "user@example.test")
        forbidden_refresh = await client.post(
            "/api/v1/admin/ai-model/refresh",
            headers={"X-CSRF-Token": user_csrf},
            json={"provider": "openai_api"},
        )
        assert forbidden_refresh.status_code == 403

        await admin_login(client)
        missing_csrf = await client.post(
            "/api/v1/admin/ai-model/custom-model",
            json={"provider": "openai_api", "model": "gpt-5.6-sol"},
        )
        assert missing_csrf.status_code == 403
