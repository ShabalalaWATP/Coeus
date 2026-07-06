import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app

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
):
    return await client.post(
        f"/api/v1/tickets/{ticket_id}/collaborators",
        headers={"X-CSRF-Token": csrf},
        json={"username": username, "access": access},
    )


@pytest.mark.asyncio
async def test_directory_lists_active_users_without_self() -> None:
    async with _client() as client:
        await _login(client, "user@example.test")
        response = await client.get("/api/v1/users/directory")

        assert response.status_code == 200
        usernames = [user["username"] for user in response.json()["users"]]
        assert "user@example.test" not in usernames
        assert "disabled@example.test" not in usernames
        assert "analyst@example.test" in usernames


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
