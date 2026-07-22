from dataclasses import replace
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.enums import TicketState
from coeus.domain.tickets import AgentRunStatus
from coeus.main import create_app
from rfi_search_helpers import login, submitted_ticket


@pytest.mark.asyncio
async def test_rfi_search_completes_when_queued_agent_run_is_missing() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(client, str(user["csrfToken"]))
        requester = app.state.access_services.repository.get_user_by_username("user@example.test")
        assert requester is not None
        ticket = app.state.ticket_services.tickets.get_visible_ticket(requester, UUID(ticket_id))
        app.state.ticket_services.tickets.save_system_update(
            replace(
                ticket,
                state=TicketState.RFI_SEARCHING,
                agent_runs=(),
                product_offers=(),
                search_metrics=(),
            )
        )
        response = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )

    assert response.status_code == 200
    assert response.json()["metrics"]["runId"]


@pytest.mark.asyncio
async def test_rfi_search_normalises_legacy_queued_agent_run_name() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(client, str(user["csrfToken"]))
        requester = app.state.access_services.repository.get_user_by_username("user@example.test")
        assert requester is not None
        ticket = app.state.ticket_services.tickets.get_visible_ticket(requester, UUID(ticket_id))
        legacy_run = replace(ticket.agent_runs[-1], agent_name="rfi-search")
        app.state.ticket_services.tickets.save_system_update(
            replace(
                ticket,
                state=TicketState.RFI_SEARCHING,
                agent_runs=(
                    *ticket.agent_runs[:-1],
                    replace(legacy_run, status=AgentRunStatus.QUEUED),
                ),
                product_offers=(),
                search_metrics=(),
            )
        )
        response = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )
        refreshed = app.state.ticket_services.tickets.get_visible_ticket(requester, UUID(ticket_id))

    assert response.status_code == 200
    assert refreshed.agent_runs[-1].agent_name == "rfi-search-agent"
