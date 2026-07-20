"""Provider activation, admin-wide notifications and connection testing."""

import pytest

from ai_model_helpers import FakeLlmClient, admin_login, make_client


@pytest.mark.asyncio
async def test_provider_activation_requires_a_key_and_notifies_all_admins() -> None:
    async with make_client() as client:
        csrf = await admin_login(client)

        unconfigured = await client.put(
            "/api/v1/admin/ai-model/provider",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "openai_api"},
        )
        assert unconfigured.status_code == 422
        assert unconfigured.json()["error"]["code"] == "provider_not_configured"

        unknown = await client.put(
            "/api/v1/admin/ai-model/provider",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "carrier_pigeon"},
        )
        assert unknown.status_code == 422
        assert unknown.json()["error"]["code"] == "provider_not_available"

        await client.put(
            "/api/v1/admin/ai-model/api-key",
            headers={"X-CSRF-Token": csrf},
            json={"apiKey": "sk-openai-key-value", "provider": "openai_api"},
        )
        activated = await client.put(
            "/api/v1/admin/ai-model/provider",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "openai_api"},
        )
        assert activated.status_code == 200
        assert activated.json()["provider"] == "openai_api"
        assert activated.json()["activeModel"] == "gpt-5.6-terra"
        assert "gpt-5.6-sol" in activated.json()["availableModels"]

        # A repeat activation is a no-op and must not renotify.
        repeated = await client.put(
            "/api/v1/admin/ai-model/provider",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "openai_api"},
        )
        assert repeated.status_code == 200

        notifications = await client.get("/api/v1/notifications")
        assert notifications.status_code == 200
        provider_notes = [
            note
            for note in notifications.json()["notifications"]
            if note["kind"] == "ai_provider_changed"
        ]
        assert len(provider_notes) == 1
        assert "OpenAI API" in provider_notes[0]["body"]
        assert "every user" in provider_notes[0]["body"]

        # Non-admins are not notified about provider changes.
        await admin_login(client, "user@example.test")
        user_notes = await client.get("/api/v1/notifications")
        assert all(
            note["kind"] != "ai_provider_changed" for note in user_notes.json()["notifications"]
        )


@pytest.mark.asyncio
async def test_connection_test_reports_key_state_and_provider_reachability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with make_client() as client:
        csrf = await admin_login(client)

        mock_result = await client.post(
            "/api/v1/admin/ai-model/test",
            headers={"X-CSRF-Token": csrf},
            json={},
        )
        assert mock_result.status_code == 200
        assert mock_result.json()["ok"] is True
        assert mock_result.json()["provider"] == "mock"

        keyless = await client.post(
            "/api/v1/admin/ai-model/test",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "bedrock"},
        )
        assert keyless.status_code == 200
        assert keyless.json()["ok"] is False
        assert "No API key" in keyless.json()["message"]

        unknown = await client.post(
            "/api/v1/admin/ai-model/test",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "carrier_pigeon"},
        )
        assert unknown.status_code == 422

        monkeypatch.setattr("coeus.integrations.provider_http.httpx.Client", FakeLlmClient)
        await client.put(
            "/api/v1/admin/ai-model/api-key",
            headers={"X-CSRF-Token": csrf},
            json={"apiKey": "gemini-api-key-value", "provider": "gemini_api"},
        )
        reachable = await client.post(
            "/api/v1/admin/ai-model/test",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "gemini_api"},
        )
        assert reachable.status_code == 200
        assert reachable.json()["ok"] is True
        assert reachable.json()["model"] == "gemini-3.5-flash"

        class FailingClient:
            def __init__(self, *, timeout: int) -> None:
                pass

            def __enter__(self) -> "FailingClient":
                return self

            def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
                return None

            def stream(
                self,
                method: str,
                url: str,
                *,
                json: object,
                headers: object,
            ) -> object:
                del method, url, json, headers
                import httpx

                raise httpx.ConnectError("mock network failure")

        monkeypatch.setattr("coeus.integrations.provider_http.httpx.Client", FailingClient)
        unreachable = await client.post(
            "/api/v1/admin/ai-model/test",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "gemini_api"},
        )
        assert unreachable.status_code == 200
        assert unreachable.json()["ok"] is False
        assert "unavailable" in unreachable.json()["message"]


@pytest.mark.asyncio
async def test_connection_test_flags_an_empty_provider_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class EmptyReplyClient(FakeLlmClient):
        def iter_bytes(self):  # type: ignore[no-untyped-def]
            import json

            yield json.dumps({"candidates": []}).encode()

    monkeypatch.setattr("coeus.integrations.provider_http.httpx.Client", EmptyReplyClient)
    async with make_client() as client:
        csrf = await admin_login(client)
        await client.put(
            "/api/v1/admin/ai-model/api-key",
            headers={"X-CSRF-Token": csrf},
            json={"apiKey": "gemini-api-key-value", "provider": "gemini_api"},
        )
        empty = await client.post(
            "/api/v1/admin/ai-model/test",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "gemini_api"},
        )

    assert empty.status_code == 200
    assert empty.json()["ok"] is False
    assert "no usable text" in empty.json()["message"]
