from pathlib import Path
from typing import cast

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app

SEED_CREDENTIAL = "CoeusLocal1!"


async def _login(client: AsyncClient, username: str = "user@example.test") -> dict[str, object]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": SEED_CREDENTIAL},
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    return cast(dict[str, object], payload)


def _persistent_settings(path: Path) -> Settings:
    return Settings(
        environment="test",
        argon2_memory_cost=8_192,
        persistence_provider="file",
        persistence_path=str(path),
        configuration_encryption_key="test-persistent-configuration-key-0001",
    )


@pytest.mark.asyncio
async def test_file_persistence_survives_app_restart(tmp_path: Path) -> None:
    state_path = tmp_path / "coeus-state.json"
    first_app = create_app(_persistent_settings(state_path))
    async with AsyncClient(
        transport=ASGITransport(app=first_app),
        base_url="http://testserver",
    ) as client:
        session = await _login(client)
        created = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={"message": "Need a routine brief for Baltic ports by Friday."},
        )
        assert created.status_code == 201
        ticket_id = created.json()["id"]

    second_app = create_app(_persistent_settings(state_path))
    async with AsyncClient(
        transport=ASGITransport(app=second_app),
        base_url="http://testserver",
    ) as client:
        await _login(client)
        listed = await client.get("/api/v1/tickets")

    assert listed.status_code == 200
    ticket_ids = {ticket["id"] for ticket in listed.json()["tickets"]}
    assert ticket_id in ticket_ids


@pytest.mark.asyncio
async def test_provider_voice_models_and_encrypted_keys_survive_app_restart(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "coeus-state.json"
    settings = _persistent_settings(state_path)
    first_app = create_app(settings)
    async with AsyncClient(
        transport=ASGITransport(app=first_app), base_url="http://testserver"
    ) as client:
        session = await _login(client, "admin@example.test")
        headers = {"X-CSRF-Token": str(session["csrfToken"])}
        assert (
            await client.put(
                "/api/v1/admin/ai-model/api-key",
                headers=headers,
                json={"provider": "openai_api", "apiKey": "sk-persistent-text-key"},
            )
        ).status_code == 200
        assert (
            await client.put(
                "/api/v1/admin/ai-model",
                headers=headers,
                json={"provider": "openai_api", "model": "gpt-5.6-sol"},
            )
        ).status_code == 200
        assert (
            await client.put(
                "/api/v1/admin/ai-model/provider",
                headers=headers,
                json={"provider": "openai_api"},
            )
        ).status_code == 200
        assert (
            await client.put(
                "/api/v1/admin/voice-model/api-key",
                headers=headers,
                json={"apiKey": "sk-persistent-voice-key"},
            )
        ).status_code == 200
        assert (
            await client.put(
                "/api/v1/admin/voice-model",
                headers=headers,
                json={"model": "gpt-realtime-mini", "enabled": True},
            )
        ).status_code == 200

    persisted = state_path.read_text(encoding="utf-8")
    assert "sk-persistent-text-key" not in persisted
    assert "sk-persistent-voice-key" not in persisted

    second_app = create_app(settings)
    async with AsyncClient(
        transport=ASGITransport(app=second_app), base_url="http://testserver"
    ) as client:
        await _login(client, "admin@example.test")
        ai_state = (await client.get("/api/v1/admin/ai-model")).json()
        voice_state = (await client.get("/api/v1/admin/voice-model")).json()

    assert ai_state["provider"] == "openai_api"
    assert ai_state["activeModel"] == "gpt-5.6-sol"
    assert ai_state["apiKeyConfigured"] is True
    assert voice_state["model"] == "gpt-realtime-mini"
    assert voice_state["enabled"] is True
    assert voice_state["apiKeyConfigured"] is True
