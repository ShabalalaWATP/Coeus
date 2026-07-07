from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app

SEED_CREDENTIAL = "CoeusLocal1!"


async def _login(client: AsyncClient) -> dict[str, object]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "user@example.test", "password": SEED_CREDENTIAL},
    )
    assert response.status_code == 200
    return response.json()


def _persistent_settings(path: Path) -> Settings:
    return Settings(
        environment="test",
        argon2_memory_cost=8_192,
        persistence_provider="file",
        persistence_path=str(path),
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
