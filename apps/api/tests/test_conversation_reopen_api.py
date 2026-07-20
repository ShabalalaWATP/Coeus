import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from ticket_api_helpers import login

COMPLETE_MESSAGE = (
    "Need a report titled Harbour Watch for the Baltic from 2026-06-01 to "
    "2026-07-01, routine priority, for Carrier Strike Group Atlas, satellite "
    "imagery preferred. Which ports are seeing unusual vessel activity? "
    "Success criteria: include likely origin ports."
)


@pytest.mark.asyncio
async def test_closed_draft_conversation_can_be_reopened_before_submission() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client)
        csrf_headers = {"X-CSRF-Token": str(session["csrfToken"])}
        created = await client.post(
            "/api/v1/chat/messages",
            headers=csrf_headers,
            json={"message": COMPLETE_MESSAGE},
        )
        ticket_id = created.json()["id"]
        closed = await client.post(
            "/api/v1/chat/messages",
            headers=csrf_headers,
            json={"ticketId": ticket_id, "message": "No, that's all thanks"},
        )
        missing_csrf = await client.post(f"/api/v1/tickets/{ticket_id}/conversation/reopen")
        reopened = await client.post(
            f"/api/v1/tickets/{ticket_id}/conversation/reopen",
            headers=csrf_headers,
        )
        continued = await client.post(
            "/api/v1/chat/messages",
            headers=csrf_headers,
            json={"ticketId": ticket_id, "message": "Also compare with last month."},
        )
        reclosed = await client.post(
            "/api/v1/chat/messages",
            headers=csrf_headers,
            json={"ticketId": ticket_id, "message": "No, finish here"},
        )
        submitted = await client.post(
            f"/api/v1/tickets/{ticket_id}/submit",
            headers=csrf_headers,
        )
        too_late = await client.post(
            f"/api/v1/tickets/{ticket_id}/conversation/reopen",
            headers=csrf_headers,
        )

    assert closed.json()["conversationStatus"] == "closed"
    assert missing_csrf.status_code == 403
    assert reopened.status_code == 200
    assert reopened.json()["conversationStatus"] == "open"
    assert reopened.json()["timeline"][-1]["eventType"] == "conversation_reopened"
    assert continued.json()["conversationStatus"] == "close_offered"
    assert reclosed.json()["conversationStatus"] == "closed"
    assert submitted.json()["state"] == "RFI_SEARCH_INCOMPLETE"
    assert too_late.status_code == 409
    assert too_late.json()["error"]["code"] == "ticket_not_editable"
