from typing import Any

import pytest

from ai_model_helpers import admin_login, make_client


@pytest.mark.asyncio
async def test_admin_configures_voice_separately_from_text_provider() -> None:
    async with make_client() as client:
        csrf = await admin_login(client)
        initial = await client.get("/api/v1/admin/voice-model")
        assert initial.status_code == 200
        assert initial.json() == {
            "model": "gpt-realtime-mini",
            "availableModels": ["gpt-realtime-mini"],
            "enabled": False,
            "apiKeyConfigured": False,
        }
        invalid_model = await client.put(
            "/api/v1/admin/voice-model",
            headers={"X-CSRF-Token": csrf},
            json={"model": "gpt-realtime-old", "enabled": False},
        )
        assert invalid_model.status_code == 422
        assert invalid_model.json()["error"]["code"] == "voice_model_not_available"

        missing_key = await client.put(
            "/api/v1/admin/voice-model",
            headers={"X-CSRF-Token": csrf},
            json={"model": "gpt-realtime-mini", "enabled": True},
        )
        assert missing_key.status_code == 422
        assert missing_key.json()["error"]["code"] == "voice_provider_not_configured"

        await client.put(
            "/api/v1/admin/ai-model/api-key",
            headers={"X-CSRF-Token": csrf},
            json={"apiKey": "sk-openai-key-value", "provider": "openai_api"},
        )
        still_missing_voice_key = await client.put(
            "/api/v1/admin/voice-model",
            headers={"X-CSRF-Token": csrf},
            json={"model": "gpt-realtime-mini", "enabled": True},
        )
        assert still_missing_voice_key.status_code == 422
        voice_key = await client.put(
            "/api/v1/admin/voice-model/api-key",
            headers={"X-CSRF-Token": csrf},
            json={"apiKey": "sk-dedicated-voice-key"},
        )
        assert voice_key.status_code == 200
        assert voice_key.json()["apiKeyConfigured"] is True
        configured = await client.put(
            "/api/v1/admin/voice-model",
            headers={"X-CSRF-Token": csrf},
            json={"model": "gpt-realtime-mini", "enabled": True},
        )
        assert configured.status_code == 200
        assert configured.json()["enabled"] is True
        ai_state = await client.get("/api/v1/admin/ai-model")
        assert ai_state.json()["provider"] == "mock"


@pytest.mark.asyncio
async def test_voice_configuration_requires_admin_and_csrf() -> None:
    async with make_client() as client:
        user_csrf = await admin_login(client, "user@example.test")
        forbidden = await client.get("/api/v1/admin/voice-model")
        assert forbidden.status_code == 403
        forbidden_update = await client.put(
            "/api/v1/admin/voice-model",
            headers={"X-CSRF-Token": user_csrf},
            json={"model": "gpt-realtime-mini", "enabled": False},
        )
        assert forbidden_update.status_code == 403
        forbidden_key = await client.put(
            "/api/v1/admin/voice-model/api-key",
            headers={"X-CSRF-Token": user_csrf},
            json={"apiKey": "sk-dedicated-voice-key"},
        )
        assert forbidden_key.status_code == 403
        forbidden_test = await client.post(
            "/api/v1/admin/voice-model/test",
            headers={"X-CSRF-Token": user_csrf},
        )
        assert forbidden_test.status_code == 403

        admin_csrf = await admin_login(client)
        missing_csrf = await client.put(
            "/api/v1/admin/voice-model",
            json={"model": "gpt-realtime-mini", "enabled": False},
        )
        assert missing_csrf.status_code == 403
        missing_key_csrf = await client.put(
            "/api/v1/admin/voice-model/api-key",
            json={"apiKey": "sk-dedicated-voice-key"},
        )
        assert missing_key_csrf.status_code == 403
        missing_test_csrf = await client.post("/api/v1/admin/voice-model/test")
        assert missing_test_csrf.status_code == 403
        invalid_key = await client.put(
            "/api/v1/admin/voice-model/api-key",
            headers={"X-CSRF-Token": admin_csrf},
            json={"apiKey": "short"},
        )
        assert invalid_key.status_code == 422


@pytest.mark.asyncio
async def test_admin_tests_voice_without_enabling_it() -> None:
    captured: dict[str, str] = {}

    def fake_test(**kwargs: str) -> None:
        captured.update(kwargs)

    def inject_tester(app: Any) -> Any:
        app.state.voice_model_service._connection_tester = fake_test
        return app

    async with make_client(app_wrapper=inject_tester) as client:
        csrf = await admin_login(client)
        missing = await client.post(
            "/api/v1/admin/voice-model/test", headers={"X-CSRF-Token": csrf}
        )
        assert missing.status_code == 200
        assert missing.json()["ok"] is False

        await client.put(
            "/api/v1/admin/voice-model/api-key",
            headers={"X-CSRF-Token": csrf},
            json={"apiKey": "sk-dedicated-voice-key"},
        )
        tested = await client.post("/api/v1/admin/voice-model/test", headers={"X-CSRF-Token": csrf})
        assert tested.status_code == 200
        assert tested.json() == {
            "ok": True,
            "provider": "openai_realtime",
            "model": "gpt-realtime-mini",
            "message": "OpenAI Realtime accepted gpt-realtime-mini.",
        }
        assert captured == {
            "api_key": "sk-dedicated-voice-key",
            "model": "gpt-realtime-mini",
        }
        state = await client.get("/api/v1/admin/voice-model")
        assert state.json()["enabled"] is False


@pytest.mark.asyncio
async def test_voice_session_validates_sdp_and_proxies_without_exposing_key() -> None:
    captured: dict[str, Any] = {}

    def fake_call(**kwargs: Any) -> str:
        captured.update(kwargs)
        return "v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"

    def inject_call_creator(app: Any) -> Any:
        app.state.voice_session_service._call_creator = fake_call
        return app

    async with make_client(app_wrapper=inject_call_creator) as client:
        admin_csrf = await admin_login(client)
        await client.put(
            "/api/v1/admin/voice-model/api-key",
            headers={"X-CSRF-Token": admin_csrf},
            json={"apiKey": "sk-dedicated-voice-key"},
        )
        await client.put(
            "/api/v1/admin/voice-model",
            headers={"X-CSRF-Token": admin_csrf},
            json={"model": "gpt-realtime-mini", "enabled": True},
        )
        user_csrf = await admin_login(client, "user@example.test")

        wrong_type = await client.post(
            "/api/v1/voice/session",
            content="v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n",
            headers={"Content-Type": "text/plain", "X-CSRF-Token": user_csrf},
        )
        assert wrong_type.status_code == 415
        invalid = await client.post(
            "/api/v1/voice/session",
            content="not-sdp",
            headers={"Content-Type": "application/sdp", "X-CSRF-Token": user_csrf},
        )
        assert invalid.status_code == 422
        invalid_utf8 = await client.post(
            "/api/v1/voice/session",
            content=b"\xff\xfe",
            headers={"Content-Type": "application/sdp", "X-CSRF-Token": user_csrf},
        )
        assert invalid_utf8.status_code == 422

        customer_config = await client.get("/api/v1/voice/config")
        assert customer_config.status_code == 200
        assert customer_config.json()["enabled"] is True

        origin = "http://127.0.0.1:5173"
        preflight = await client.options(
            "/api/v1/voice/session",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-csrf-token",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == origin
        assert "POST" in preflight.headers["access-control-allow-methods"]

        response = await client.post(
            "/api/v1/voice/session",
            content="v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n",
            headers={
                "Content-Type": "application/sdp",
                "Origin": origin,
                "X-CSRF-Token": user_csrf,
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
        assert response.headers["access-control-expose-headers"] == "X-Voice-Session-Token"
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["content-type"].startswith("application/sdp")
        token = response.headers["x-voice-session-token"]
        assert captured["model"] == "gpt-realtime-mini"
        assert "YOUR ONLY PURPOSE" in captured["instructions"]
        assert "NEVER say the RFI was created, saved" in captured["instructions"]
        assert captured["api_key"] == "sk-dedicated-voice-key"
        assert len(captured["safety_identifier"]) == 64

        capacity = await client.post(
            "/api/v1/voice/session",
            content="v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n",
            headers={"Content-Type": "application/sdp", "X-CSRF-Token": user_csrf},
        )
        assert capacity.status_code == 429
        released = await client.delete(
            f"/api/v1/voice/session/{token}", headers={"X-CSRF-Token": user_csrf}
        )
        assert released.status_code == 204


@pytest.mark.asyncio
async def test_voice_session_rejects_missing_csrf_and_oversized_offer() -> None:
    async with make_client() as client:
        csrf = await admin_login(client, "user@example.test")
        missing_csrf = await client.post(
            "/api/v1/voice/session",
            content="v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n",
            headers={"Content-Type": "application/sdp"},
        )
        assert missing_csrf.status_code == 403
        oversized = await client.post(
            "/api/v1/voice/session",
            content="v=0\r\nm=audio " + ("x" * 65_536),
            headers={"Content-Type": "application/sdp", "X-CSRF-Token": csrf},
        )
        assert oversized.status_code == 413

        async def streamed_oversized_offer():
            yield b"v=0\r\nm=audio "
            yield b"x" * 65_536

        streamed = await client.post(
            "/api/v1/voice/session",
            content=streamed_oversized_offer(),
            headers={"Content-Type": "application/sdp", "X-CSRF-Token": csrf},
        )
        assert streamed.status_code == 413
