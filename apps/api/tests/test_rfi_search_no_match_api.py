import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login


@pytest.mark.asyncio
async def test_no_match_search_requires_customer_consent_before_route_review() -> None:
    app = create_app(_settings())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await _no_match_ticket(client, str(user["csrfToken"]))
        search = await _run_no_match_search(client, ticket_id, str(user["csrfToken"]))
        tickets = await client.get("/api/v1/tickets")
        consent = await client.post(
            f"/api/v1/tickets/{ticket_id}/no-match-consent",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={"taskAsNewRequest": True},
        )
        manager = await login(client, "rfa.manager@example.test")
        routed = await client.post(
            f"/api/v1/routing/{ticket_id}/run",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )

    ticket = _ticket_payload(tickets.json(), ticket_id)
    assert search.json()["ticketState"] == "RFI_NO_MATCH"
    assert search.json()["offers"] == []
    assert search.json()["metrics"]["offeredCount"] == 0
    assert ticket["state"] == "RFI_NO_MATCH"
    assert _timeline_bodies(ticket, "rfi_no_match") == ["No existing product matched this request."]
    assert consent.status_code == 200
    assert consent.json()["state"] == "ROUTE_ASSESSMENT"
    assert _timeline_bodies(consent.json(), "tasking_confirmed") == [
        "Requester confirmed tasking as a new request."
    ]
    assert routed.status_code == 200
    assert routed.json()["rfaReview"] is not None
    assert "no_match_tasking_confirmed" in _audit_types(app)


@pytest.mark.asyncio
async def test_no_match_decline_cancels_with_fixed_reason() -> None:
    app = create_app(_settings())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await _no_match_ticket(client, str(user["csrfToken"]))
        await _run_no_match_search(client, ticket_id, str(user["csrfToken"]))
        declined = await client.post(
            f"/api/v1/tickets/{ticket_id}/no-match-consent",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={"taskAsNewRequest": False},
        )

    assert declined.status_code == 200
    assert declined.json()["state"] == "CANCELLED"
    assert _timeline_bodies(declined.json(), "tasking_declined") == [
        "customer declined tasking after no-match"
    ]
    assert "no_match_tasking_declined" in _audit_types(app)


@pytest.mark.asyncio
async def test_no_match_consent_is_owner_only_and_state_bound() -> None:
    app = create_app(_settings())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        wrong_state_id = await _no_match_ticket(client, str(user["csrfToken"]))
        wrong_state = await client.post(
            f"/api/v1/tickets/{wrong_state_id}/no-match-consent",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={"taskAsNewRequest": True},
        )
        ticket_id = await _no_match_ticket(client, str(user["csrfToken"]))
        await _run_no_match_search(client, ticket_id, str(user["csrfToken"]))
        collaborator = await client.post(
            f"/api/v1/tickets/{ticket_id}/collaborators",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={"username": "colleague@example.test", "access": "viewer"},
        )
        colleague = await login(client, "colleague@example.test")
        forbidden = await client.post(
            f"/api/v1/tickets/{ticket_id}/no-match-consent",
            headers={"X-CSRF-Token": str(colleague["csrfToken"])},
            json={"taskAsNewRequest": True},
        )

    assert wrong_state.status_code == 409
    assert wrong_state.json()["error"]["code"] == "invalid_ticket_state"
    assert collaborator.status_code == 200
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"


def _settings() -> Settings:
    return Settings(
        environment="test",
        argon2_memory_cost=8_192,
        persistence_provider="memory",
    )


async def _no_match_ticket(client: AsyncClient, csrf_token: str) -> str:
    created = await client.post(
        "/api/v1/chat/messages",
        headers={"X-CSRF-Token": csrf_token},
        json={"message": "Need a spreadsheet forecast for mock Martian crop yields."},
    )
    ticket_id = created.json()["id"]
    edited = await client.patch(
        f"/api/v1/tickets/{ticket_id}/intake",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "title": "Martian Crop Forecast",
            "description": "Forecast mock agricultural yields on Mars farms.",
            "operationalQuestion": "What crop yield is expected?",
            "areaOrRegion": "Mars farms",
            "priority": "routine",
            "requiredOutputFormat": "spreadsheet",
            "customerSuccessCriteria": "Estimate crop output.",
            "knownContext": None,
        },
    )
    submitted = await client.post(
        f"/api/v1/tickets/{ticket_id}/submit",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert created.status_code == 201
    assert edited.status_code == 200
    assert submitted.status_code == 200
    return str(ticket_id)


async def _run_no_match_search(client: AsyncClient, ticket_id: str, csrf_token: str):
    response = await client.post(
        f"/api/v1/rfi-search/{ticket_id}/run",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200
    return response


def _ticket_payload(payload: dict[str, object], ticket_id: str) -> dict[str, object]:
    tickets = payload["tickets"]
    assert isinstance(tickets, list)
    return next(ticket for ticket in tickets if ticket["id"] == ticket_id)


def _timeline_bodies(ticket: dict[str, object], event_type: str) -> list[str]:
    timeline = ticket["timeline"]
    assert isinstance(timeline, list)
    return [item["body"] for item in timeline if item["eventType"] == event_type]


def _audit_types(app: object) -> list[str]:
    return [event.event_type for event in app.state.auth_service.audit_log.list_events()]
