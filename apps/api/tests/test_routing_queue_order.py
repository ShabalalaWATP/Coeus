import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login
from routing_helpers import route_assessment_ticket


@pytest.mark.asyncio
async def test_jioc_queue_orders_by_internal_priority_before_age() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        # The lower-priority region ticket is created FIRST (older).
        standard_id = await route_assessment_ticket(
            client,
            str(user["csrfToken"]),
            title="Atlantic Seaboard Assessment",
            area_or_region="Atlantic seaboard",
            output_format="assessment report",
        )
        arctic_id = await route_assessment_ticket(
            client,
            str(user["csrfToken"]),
            title="Arctic Fisheries Assessment",
            area_or_region="Arctic fisheries",
            output_format="assessment report",
        )
        await login(client, "jioc.team@example.test")
        queue = await client.get("/api/v1/routing/jioc/queue")

    assert queue.status_code == 200
    tickets = queue.json()["tickets"]
    # The newer tier-1 Arctic ticket outranks the older standard-region one.
    assert [item["ticketId"] for item in tickets] == [arctic_id, standard_id]
    assert tickets[0]["priorityAssessment"]["tier"] in {"P1", "P2"}
    assert "priority:region:tier-1:arctic" in tickets[0]["priorityAssessment"]["reasons"]
    assert tickets[0]["priorityAssessment"]["score"] > tickets[1]["priorityAssessment"]["score"]
