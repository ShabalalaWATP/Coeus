import asyncio
from threading import Event
from typing import cast

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login, submitted_ticket
from ticket_api_helpers import stored_ticket


@pytest.mark.asyncio
async def test_rfi_search_rejects_stale_snapshot_and_preserves_concurrent_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    started = Event()
    release = Event()
    original_embed = app.state.rfi_search_service._embeddings.embed

    def delayed_embed(text: str, *, purpose: str) -> tuple[float, ...]:
        started.set()
        assert release.wait(5)
        return cast(tuple[float, ...], original_embed(text, purpose=purpose))

    monkeypatch.setattr(app.state.rfi_search_service._embeddings, "embed", delayed_embed)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "user@example.test")
        csrf = str(session["csrfToken"])
        ticket_id = await submitted_ticket(client, csrf)
        search = asyncio.create_task(
            client.post(
                f"/api/v1/rfi-search/{ticket_id}/run",
                headers={"X-CSRF-Token": csrf},
            )
        )
        assert await asyncio.to_thread(started.wait, 5)
        marker = "Concurrent synthetic clarification must survive."
        update = await client.post(
            f"/api/v1/tickets/{ticket_id}/timeline",
            headers={"X-CSRF-Token": csrf},
            json={"body": marker},
        )
        release.set()
        response = await search

    assert update.status_code == 200
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ticket_changed"
    ticket = stored_ticket(app, ticket_id)
    assert any(item.body == marker for item in ticket.timeline)
