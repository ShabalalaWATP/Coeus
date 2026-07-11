from httpx import AsyncClient

from rfi_search_helpers import login, submitted_ticket


async def route_assessment_ticket(
    client: AsyncClient,
    csrf_token: str,
    *,
    title: str = "Arctic Fisheries Assessment",
    area_or_region: str = "Arctic fisheries",
    output_format: str = "assessment report",
) -> str:
    """Walk a ticket from submission into the JIOC review queue."""
    ticket_id = await submitted_ticket(
        client,
        csrf_token,
        title=title,
        area_or_region=area_or_region,
        output_format=output_format,
    )
    response = await client.post(
        f"/api/v1/rfi-search/{ticket_id}/run",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200
    if response.json()["ticketState"] == "RFI_MATCH_OFFERED":
        for offer in response.json()["offers"]:
            response = await client.post(
                f"/api/v1/rfi-search/{ticket_id}/offers/{offer['productId']}/reject",
                headers={"X-CSRF-Token": csrf_token},
                json={"reason": "Need a new assessment route."},
            )
            assert response.status_code == 200
    assert response.json()["ticketState"] == "JIOC_REVIEW"
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
