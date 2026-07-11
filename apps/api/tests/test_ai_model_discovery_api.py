"""Refreshing models from a provider and adding models by hand."""

from typing import Any, ClassVar

import pytest

from ai_model_helpers import admin_login, make_client


class FakeModelListClient:
    """Fake httpx.Client answering the OpenAI model-listing endpoint."""

    captured: ClassVar[dict[str, Any]] = {}

    def __init__(self, *, timeout: int) -> None:
        pass

    def __enter__(self) -> "FakeModelListClient":
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        return None

    def get(self, url: str, *, headers: dict[str, str]) -> "FakeModelListClient":
        FakeModelListClient.captured["url"] = url
        return self

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {"data": [{"id": "gpt-5"}, {"id": "gpt-6-omni"}, {"id": "text-embedding-3"}]}


@pytest.mark.asyncio
async def test_refresh_loads_live_models_and_keeps_curated_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("coeus.integrations.llm_models.httpx.Client", FakeModelListClient)
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
        assert refreshed.status_code == 200
        openai = next(p for p in refreshed.json()["providers"] if p["name"] == "openai_api")
        # Curated defaults stay, the newly discovered id is appended.
        assert "gpt-5-mini" in openai["models"]
        assert "gpt-6-omni" in openai["models"]
        assert "text-embedding-3" not in openai["models"]

        # A discovered model can then be selected.
        selected = await client.put(
            "/api/v1/admin/ai-model",
            headers={"X-CSRF-Token": csrf},
            json={"model": "gpt-6-omni", "provider": "openai_api"},
        )
        assert selected.status_code == 200


@pytest.mark.asyncio
async def test_refresh_requires_a_key_and_supported_provider() -> None:
    async with make_client() as client:
        csrf = await admin_login(client)

        keyless = await client.post(
            "/api/v1/admin/ai-model/refresh",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "openai_api"},
        )
        assert keyless.status_code == 409
        assert keyless.json()["error"]["code"] == "provider_not_configured"

        await client.put(
            "/api/v1/admin/ai-model/api-key",
            headers={"X-CSRF-Token": csrf},
            json={"apiKey": "vx-key-value", "provider": "vertex_ai"},
        )
        unsupported = await client.post(
            "/api/v1/admin/ai-model/refresh",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "vertex_ai"},
        )
        assert unsupported.status_code == 422
        assert unsupported.json()["error"]["code"] == "refresh_not_supported"


@pytest.mark.asyncio
async def test_admin_adds_a_custom_model_and_it_becomes_selectable() -> None:
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
        assert bedrock["activeModel"] == "anthropic.claude-opus-5-20261101-v1:0"

        # Adding the same id again is idempotent and keeps it selected.
        again = await client.post(
            "/api/v1/admin/ai-model/custom-model",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "bedrock", "model": "anthropic.claude-opus-5-20261101-v1:0"},
        )
        assert again.status_code == 200

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
            json={"provider": "openai_api", "model": "gpt-5"},
        )
        assert missing_csrf.status_code == 403
