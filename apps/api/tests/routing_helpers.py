from httpx import AsyncClient

from rfi_search_helpers import submitted_ticket


async def route_assessment_ticket(
    client: AsyncClient,
    csrf_token: str,
    *,
    title: str = "Arctic Fisheries Assessment",
    area_or_region: str = "Arctic fisheries",
    output_format: str = "assessment report",
) -> str:
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
    assert response.json()["ticketState"] == "ROUTE_ASSESSMENT"
    return ticket_id
