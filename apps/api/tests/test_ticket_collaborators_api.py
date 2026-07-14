from typing import cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from coeus.core.config import Settings
from coeus.domain.tickets import TicketRecord
from coeus.main import create_app
from coeus.services.audit import AuditEvent

SEED_CREDENTIAL = "CoeusLocal1!"


def _client() -> AsyncClient:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _login(client: AsyncClient, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": SEED_CREDENTIAL},
    )
    assert response.status_code == 200
    return str(response.json()["csrfToken"])


async def _create_ticket(client: AsyncClient, csrf: str) -> str:
    response = await client.post(
        "/api/v1/chat/messages",
        headers={"X-CSRF-Token": csrf},
        json={"message": "Assess mock harbour activity in the Baltic."},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def _tag(
    client: AsyncClient,
    csrf: str,
    ticket_id: str,
    username: str,
    access: str,
) -> Response:
    return await client.post(
        f"/api/v1/tickets/{ticket_id}/collaborators",
        headers={"X-CSRF-Token": csrf},
        json={"username": username, "access": access},
    )


@pytest.mark.asyncio
async def test_directory_requires_a_search_term() -> None:
    async with _client() as client:
        await _login(client, "user@example.test")

        missing = await client.get("/api/v1/users/directory")
        assert missing.status_code == 422

        too_short = await client.get("/api/v1/users/directory?q=an")
        assert too_short.status_code == 422


@pytest.mark.asyncio
async def test_directory_returns_matching_active_users_without_self() -> None:
    async with _client() as client:
        await _login(client, "user@example.test")
        response = await client.get("/api/v1/users/directory?q=Analyst")

        assert response.status_code == 200
        usernames = [user["username"] for user in response.json()["users"]]
        assert "analyst@example.test" in usernames
        assert all("analyst" in username for username in usernames)

        broad = await client.get("/api/v1/users/directory?q=example")
        matched = [user["username"] for user in broad.json()["users"]]
        assert "user@example.test" not in matched
        assert "disabled@example.test" not in matched
        # Twelve active seed accounts match "example"; the response is capped.
        assert len(matched) == 10


@pytest.mark.asyncio
async def test_owner_tags_editor_who_can_view_and_edit() -> None:
    async with _client() as client:
        owner_csrf = await _login(client, "user@example.test")
        ticket_id = await _create_ticket(client, owner_csrf)

        tagged = await _tag(client, owner_csrf, ticket_id, "colleague@example.test", "editor")
        assert tagged.status_code == 200
        collaborators = tagged.json()["collaborators"]
        assert collaborators[0]["username"] == "colleague@example.test"
        assert collaborators[0]["access"] == "editor"

        editor_csrf = await _login(client, "colleague@example.test")
        listed = await client.get("/api/v1/tickets")
        assert ticket_id in [ticket["id"] for ticket in listed.json()["tickets"]]

        chat = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": editor_csrf},
            json={"ticketId": ticket_id, "message": "Adding sensor context for the request."},
        )
        assert chat.status_code == 201

        intake = await client.patch(
            f"/api/v1/tickets/{ticket_id}/intake",
            headers={"X-CSRF-Token": editor_csrf},
            json={"priority": "routine"},
        )
        assert intake.status_code == 200


@pytest.mark.asyncio
async def test_editor_can_complete_intake_but_cannot_submit_owner_ticket() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        owner_csrf = await _login(client, "user@example.test")
        ticket_id = await _create_ticket(client, owner_csrf)
        await _tag(client, owner_csrf, ticket_id, "colleague@example.test", "editor")

        editor_csrf = await _login(client, "colleague@example.test")
        completed = await client.patch(
            f"/api/v1/tickets/{ticket_id}/intake",
            headers={"X-CSRF-Token": editor_csrf},
            json={
                "title": "Mock Collaborative Assessment",
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
        before = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
        before_events = app.state.auth_service.audit_log.list_events()
        denied = await client.post(
            f"/api/v1/tickets/{ticket_id}/submit",
            headers={"X-CSRF-Token": editor_csrf},
        )
        after = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
        after_denied_events = app.state.auth_service.audit_log.list_events()

        owner_csrf = await _login(client, "user@example.test")
        owner_submit = await client.post(
            f"/api/v1/tickets/{ticket_id}/submit",
            headers={"X-CSRF-Token": owner_csrf},
        )

    assert completed.status_code == 200
    assert completed.json()["isReadyForSubmission"] is True
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "ticket_not_found"
    assert after == before
    assert after_denied_events == before_events
    assert owner_submit.status_code == 200
    assert owner_submit.json()["state"] == "RFI_SEARCHING"


@pytest.mark.asyncio
async def test_viewer_can_read_but_not_edit_or_manage() -> None:
    async with _client() as client:
        owner_csrf = await _login(client, "user@example.test")
        ticket_id = await _create_ticket(client, owner_csrf)
        await _tag(client, owner_csrf, ticket_id, "colleague@example.test", "viewer")

        viewer_csrf = await _login(client, "colleague@example.test")
        listed = await client.get("/api/v1/tickets")
        assert ticket_id in [ticket["id"] for ticket in listed.json()["tickets"]]

        chat = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": viewer_csrf},
            json={"ticketId": ticket_id, "message": "Trying to edit as a viewer."},
        )
        assert chat.status_code == 404

        intake = await client.patch(
            f"/api/v1/tickets/{ticket_id}/intake",
            headers={"X-CSRF-Token": viewer_csrf},
            json={"priority": "routine"},
        )
        assert intake.status_code == 404

        information = await client.post(
            f"/api/v1/tickets/{ticket_id}/timeline",
            headers={"X-CSRF-Token": viewer_csrf},
            json={"body": "Trying to add information as a viewer."},
        )
        assert information.status_code == 404

        manage = await _tag(client, viewer_csrf, ticket_id, "qc.manager@example.test", "viewer")
        assert manage.status_code == 404


@pytest.mark.asyncio
async def test_invalid_collaborators_are_rejected_generically() -> None:
    async with _client() as client:
        owner_csrf = await _login(client, "user@example.test")
        ticket_id = await _create_ticket(client, owner_csrf)

        unknown = await _tag(client, owner_csrf, ticket_id, "ghost@example.test", "viewer")
        disabled = await _tag(client, owner_csrf, ticket_id, "disabled@example.test", "viewer")
        own = await _tag(client, owner_csrf, ticket_id, "user@example.test", "editor")

        for response in (unknown, disabled, own):
            assert response.status_code == 422
            assert response.json()["error"]["code"] == "collaborator_invalid"

        bad_access = await _tag(client, owner_csrf, ticket_id, "analyst@example.test", "owner")
        assert bad_access.status_code == 422


@pytest.mark.asyncio
async def test_retagging_updates_access_and_remove_revokes_visibility() -> None:
    async with _client() as client:
        owner_csrf = await _login(client, "user@example.test")
        ticket_id = await _create_ticket(client, owner_csrf)

        await _tag(client, owner_csrf, ticket_id, "colleague@example.test", "viewer")
        retagged = await _tag(client, owner_csrf, ticket_id, "colleague@example.test", "editor")
        collaborators = retagged.json()["collaborators"]
        assert len(collaborators) == 1
        assert collaborators[0]["access"] == "editor"
        colleague_user_id = collaborators[0]["userId"]

        removed = await client.delete(
            f"/api/v1/tickets/{ticket_id}/collaborators/{colleague_user_id}",
            headers={"X-CSRF-Token": owner_csrf},
        )
        assert removed.status_code == 200
        assert removed.json()["collaborators"] == []

        missing = await client.delete(
            f"/api/v1/tickets/{ticket_id}/collaborators/{colleague_user_id}",
            headers={"X-CSRF-Token": owner_csrf},
        )
        assert missing.status_code == 404

        await _login(client, "colleague@example.test")
        listed = await client.get("/api/v1/tickets")
        assert ticket_id not in [ticket["id"] for ticket in listed.json()["tickets"]]


@pytest.mark.asyncio
async def test_collaborator_mutations_require_csrf() -> None:
    async with _client() as client:
        owner_csrf = await _login(client, "user@example.test")
        ticket_id = await _create_ticket(client, owner_csrf)

        response = await client.post(
            f"/api/v1/tickets/{ticket_id}/collaborators",
            json={"username": "analyst@example.test", "access": "viewer"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "csrf_failed"


@pytest.mark.asyncio
async def test_add_collaborator_audit_failure_rolls_back_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        owner_csrf = await _login(client, "user@example.test")
        ticket_id = await _create_ticket(client, owner_csrf)
        original = _stored_ticket(app, ticket_id)
        monkeypatch.setattr(app.state.ticket_collaborator_service._audit_log, "record", _fail_audit)

        with pytest.raises(RuntimeError, match="audit unavailable"):
            await _tag(client, owner_csrf, ticket_id, "colleague@example.test", "editor")

    ticket = _stored_ticket(app, ticket_id)
    assert ticket.collaborators == original.collaborators
    assert ticket.timeline == original.timeline


@pytest.mark.asyncio
async def test_remove_collaborator_audit_failure_rolls_back_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        owner_csrf = await _login(client, "user@example.test")
        ticket_id = await _create_ticket(client, owner_csrf)
        tagged = await _tag(client, owner_csrf, ticket_id, "colleague@example.test", "viewer")
        collaborator_id = tagged.json()["collaborators"][0]["userId"]
        original = _stored_ticket(app, ticket_id)
        monkeypatch.setattr(app.state.ticket_collaborator_service._audit_log, "record", _fail_audit)

        with pytest.raises(RuntimeError, match="audit unavailable"):
            await client.delete(
                f"/api/v1/tickets/{ticket_id}/collaborators/{collaborator_id}",
                headers={"X-CSRF-Token": owner_csrf},
            )

    ticket = _stored_ticket(app, ticket_id)
    assert ticket.collaborators == original.collaborators
    assert ticket.timeline == original.timeline


def _fail_audit(
    event_type: str,
    actor_user_id: str | None = None,
    metadata: dict[str, str] | None = None,
) -> AuditEvent:
    raise RuntimeError("audit unavailable")


def _stored_ticket(app: FastAPI, ticket_id: str) -> TicketRecord:
    ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert ticket is not None
    return cast(TicketRecord, ticket)
