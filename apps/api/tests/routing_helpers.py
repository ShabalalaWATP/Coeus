from dataclasses import replace
from uuid import UUID

from httpx import ASGITransport, AsyncClient

from coeus.domain.enums import TicketState
from rfi_search_helpers import (
    ensure_search_index_ready,
    login,
    mark_search_complete_for_downstream_fixture,
    submitted_ticket,
)


async def route_assessment_ticket(
    client: AsyncClient,
    csrf_token: str,
    *,
    title: str = "Arctic Fisheries Assessment",
    area_or_region: str = "Arctic fisheries",
    output_format: str = "assessment report",
) -> str:
    """Walk a ticket from submission into the JIOC review queue."""
    transport = client._transport
    assert isinstance(transport, ASGITransport)
    ensure_search_index_ready(transport.app)
    ticket_id = await submitted_ticket(
        client,
        csrf_token,
        title=title,
        area_or_region=area_or_region,
        output_format=output_format,
        restrictions="Manual JIOC review required for this legacy route-review fixture.",
    )
    response = await client.get(f"/api/v1/rfi-search/{ticket_id}/results")
    if response.json()["ticketState"] in {"RFI_SEARCHING", "RFI_SEARCH_INCOMPLETE"}:
        response = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200
    if response.json()["ticketState"] == "RFI_MATCH_OFFERED":
        mark_search_complete_for_downstream_fixture(transport.app, ticket_id)
        for offer in response.json()["offers"]:
            response = await client.post(
                f"/api/v1/rfi-search/{ticket_id}/offers/{offer['productId']}/reject",
                headers={"X-CSRF-Token": csrf_token},
                json={"reason": "Need a new assessment route."},
            )
            assert response.status_code == 200
    if response.json()["ticketState"] == "ACTIVE_WORK_REVIEW":
        response = await client.post(
            f"/api/v1/similar-requests/tickets/{ticket_id}/continue",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200
    state = response.json().get("ticketState", response.json().get("state"))
    if state in {"RFI_NO_MATCH", "NEW_TASKING_CONSENT"}:
        response = await client.post(
            f"/api/v1/tickets/{ticket_id}/no-match-consent",
            headers={"X-CSRF-Token": csrf_token},
            json={"taskAsNewRequest": True},
        )
        assert response.status_code == 200
    state = response.json().get("ticketState", response.json().get("state"))
    if state != "JIOC_REVIEW":
        app = transport.app
        ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
        assert ticket is not None
        app.state.ticket_services.tickets.save_system_update(
            replace(ticket, state=TicketState.JIOC_REVIEW)
        )
    return ticket_id


async def analyst_assignment_ticket(
    client: AsyncClient,
    *,
    title: str = "Arctic Fisheries Assessment",
    area_or_region: str = "Arctic fisheries",
    output_format: str = "assessment report",
) -> str:
    """Walk a ticket through JIOC approval onto the RFA team's queue."""
    user = await login(client, "user@example.test")
    ticket_id = await route_assessment_ticket(
        client,
        str(user["csrfToken"]),
        title=title,
        area_or_region=area_or_region,
        output_format=output_format,
    )
    jioc = await login(client, "jioc.team@example.test")
    routed = await client.post(
        f"/api/v1/routing/{ticket_id}/run",
        headers={"X-CSRF-Token": str(jioc["csrfToken"])},
    )
    approved = await client.post(
        f"/api/v1/routing/{ticket_id}/approve",
        headers={"X-CSRF-Token": str(jioc["csrfToken"])},
        json={"route": "rfa"},
    )
    assert routed.status_code == 200
    assert approved.status_code == 200
    assert approved.json()["state"] == "ANALYST_ASSIGNMENT"
    return ticket_id


async def assignment_team_id(client: AsyncClient, route: str = "rfa") -> str:
    response = await client.get(f"/api/v1/analyst/assignment-teams?route={route}")
    assert response.status_code == 200
    return str(response.json()["teams"][0]["teamId"])
