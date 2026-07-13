"""Refreshing models from a provider and adding models by hand."""

import asyncio
import inspect
from threading import Event
from typing import Any, ClassVar

import pytest
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ai_model_helpers import admin_login, make_client
from coeus.api.routes.admin import (
    refresh_ai_models as refresh_route,
)
from coeus.api.routes.admin import (
    test_ai_connection as connection_test_route,
)


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


class LivenessObserver:
    """Expose deterministic barriers around the live-health ASGI response."""

    def __init__(
        self,
        app: ASGIApp,
        entered: asyncio.Event,
        completed: asyncio.Event,
    ) -> None:
        self._app = app
        self._entered = entered
        self._completed = completed

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") != "/api/v1/health/live":
            await self._app(scope, receive, send)
            return
        self._entered.set()

        async def observed_send(message: Message) -> None:
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                self._completed.set()

        await self._app(scope, receive, observed_send)


def test_synchronous_provider_routes_are_offloaded_by_fastapi() -> None:
    assert not inspect.iscoroutinefunction(refresh_route)
    assert not inspect.iscoroutinefunction(connection_test_route)


@pytest.mark.asyncio
async def test_refresh_loads_live_models_and_keeps_curated_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("coeus.integrations.provider_http.httpx.Client", FakeModelListClient)
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
        assert openai["supportsModelRefresh"] is True

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

        unsupported = await client.post(
            "/api/v1/admin/ai-model/refresh",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "vertex_ai"},
        )
        assert unsupported.status_code == 422
        assert unsupported.json()["error"]["code"] == "refresh_not_supported"

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


@pytest.mark.asyncio
async def test_slow_model_refresh_does_not_stall_liveness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = Event()
    release = Event()
    live_entered = asyncio.Event()
    live_completed = asyncio.Event()

    def delayed_discovery(*_args: object) -> tuple[str, ...]:
        started.set()
        release.wait(timeout=10)
        return ("gpt-6-responsive",)

    monkeypatch.setattr("coeus.services.ai_models.discover_models", delayed_discovery)
    async with make_client(
        app_wrapper=lambda app: LivenessObserver(app, live_entered, live_completed)
    ) as client:
        csrf = await admin_login(client)
        await client.put(
            "/api/v1/admin/ai-model/api-key",
            headers={"X-CSRF-Token": csrf},
            json={"apiKey": "sk-openai-key-value", "provider": "openai_api"},
        )
        refresh = asyncio.create_task(
            client.post(
                "/api/v1/admin/ai-model/refresh",
                headers={"X-CSRF-Token": csrf},
                json={"provider": "openai_api"},
            )
        )
        try:
            assert await asyncio.to_thread(started.wait, 5)
            liveness_request = asyncio.create_task(client.get("/api/v1/health/live"))
            await asyncio.wait_for(live_entered.wait(), timeout=5)
            await asyncio.wait_for(live_completed.wait(), timeout=5)
            liveness = await liveness_request
            assert liveness.status_code == 200
            assert not refresh.done()
        finally:
            release.set()
        assert (await refresh).status_code == 200
