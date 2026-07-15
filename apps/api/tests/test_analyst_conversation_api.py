from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login
from routing_helpers import analyst_assignment_ticket


@pytest.mark.asyncio
async def test_assigned_analyst_reads_the_complete_ordered_conversation_only() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    repository = app.state.access_services.repository
    assigned_user = repository.get_user_by_username("analyst@example.test")
    assert assigned_user is not None

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await analyst_assignment_ticket(client)
        manager = await login(client, "rfa.manager@example.test")
        team_id = next(
            team.team_id
            for team in app.state.team_repository.list_teams()
            if team.kind.value == "rfa"
        )
        assigned = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/assign",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"analystUserIds": [str(assigned_user.user_id)], "teamId": str(team_id)},
        )
        assert assigned.status_code == 200

        ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
        assert ticket is not None
        expected = [
            {"id": str(message.message_id), "author": message.author, "body": message.body}
            for message in ticket.messages
        ]

        await login(client, "analyst@example.test")
        allowed = await client.get(f"/api/v1/analyst/tasks/{ticket_id}/conversation")
        await login(client, "analyst.2@example.test")
        unassigned = await client.get(f"/api/v1/analyst/tasks/{ticket_id}/conversation")
        await login(client, "user@example.test")
        customer = await client.get(f"/api/v1/analyst/tasks/{ticket_id}/conversation")

    assert allowed.status_code == 200
    actual = [
        {key: message[key] for key in ("id", "author", "body")}
        for message in allowed.json()["messages"]
    ]
    assert actual == expected
    assert unassigned.status_code == 404
    assert customer.status_code == 403
