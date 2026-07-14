from dataclasses import replace
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.core.permissions import Permission
from coeus.main import create_app
from test_ticket_collaborators_api import _create_ticket, _login, _tag


@pytest.mark.asyncio
async def test_submission_uses_explicit_transition_authority_not_global_write() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    colleague = app.state.access_services.repository.get_user_by_username("colleague@example.test")
    assert colleague is not None

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        owner_csrf = await _login(client, "user@example.test")
        ticket_id = await _create_ticket(client, owner_csrf)
        await _tag(client, owner_csrf, ticket_id, colleague.username, "editor")
        completed = await client.patch(
            f"/api/v1/tickets/{ticket_id}/intake",
            headers={"X-CSRF-Token": owner_csrf},
            json={
                "title": "Mock Permission Matrix Assessment",
                "description": "Assess synthetic harbour activity and likely disruption.",
                "operationalQuestion": "What mock activity needs command attention?",
                "areaOrRegion": "Baltic ports",
                "timePeriodStart": "2026-07-01",
                "priority": "high",
                "supportedOperation": "Operation Mock Sentinel",
                "urgencyJustification": "A synthetic decision is due this week.",
                "deadline": "Friday",
                "requestingUnit": "Synthetic Task Group",
                "intelligenceDisciplines": "IMINT",
                "requiredOutputFormat": "Briefing note",
                "customerSuccessCriteria": "Identify mock actions for watch teams.",
            },
        )
        assert completed.json()["isReadyForSubmission"] is True

        users = app.state.auth_service._users
        users.save(replace(colleague, permissions=frozenset({Permission.TICKET_WRITE_ALL})))
        writer_csrf = await _login(client, colleague.username)
        before = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
        before_events = app.state.auth_service.audit_log.list_events()
        denied = await client.post(
            f"/api/v1/tickets/{ticket_id}/submit",
            headers={"X-CSRF-Token": writer_csrf},
        )
        after_denied_events = app.state.auth_service.audit_log.list_events()

        writer = users.get_by_id(colleague.user_id)
        assert writer is not None
        users.save(replace(writer, permissions=frozenset({Permission.TICKET_TRANSITION})))
        transition_csrf = await _login(client, colleague.username)
        allowed = await client.post(
            f"/api/v1/tickets/{ticket_id}/submit",
            headers={"X-CSRF-Token": transition_csrf},
        )

    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "ticket_not_found"
    assert after_denied_events == before_events
    assert before is not None
    assert before.state.value == "DRAFT_INTAKE"
    assert allowed.status_code == 200
    assert allowed.json()["state"] == "RFI_SEARCHING"
