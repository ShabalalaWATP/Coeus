"""The analysed-collect journey: CM leg, QC forward to RFA, RFA leg, release.

When the customer chooses "collect plus RFA analysis", QC approval of the
collect does not release it; the ticket returns to analyst assignment on the
RFA route with the collect product linked (still DRAFT), and only the RFA
leg's QC approval releases an assessment to the customer.
"""

from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.access import ProductStatus
from coeus.domain.tickets import RoutingRoute
from coeus.main import create_app
from coeus.services.analyst_records import active_assignments, approved_route
from rfi_search_helpers import login
from routing_helpers import route_assessment_ticket
from test_qc_api import _acg_id, _approval_payload, _draft_payload


def _app() -> FastAPI:
    return create_app(Settings(environment="test", argon2_memory_cost=8_192))


async def _analysed_collect_ticket(client: AsyncClient) -> str:
    user = await login(client, "user@example.test")
    ticket_id = await route_assessment_ticket(
        client,
        str(user["csrfToken"]),
        title="Analysed Sensor Collection",
        area_or_region="Arctic fisheries",
        output_format="collection plan",
    )
    jioc = await login(client, "jioc.team@example.test")
    await client.post(
        f"/api/v1/routing/{ticket_id}/run",
        headers={"X-CSRF-Token": str(jioc["csrfToken"])},
    )
    approved = await client.post(
        f"/api/v1/routing/{ticket_id}/approve",
        headers={"X-CSRF-Token": str(jioc["csrfToken"])},
        json={"route": "cm"},
    )
    assert approved.status_code == 200
    user = await login(client, "user@example.test")
    chosen = await client.post(
        f"/api/v1/tickets/{ticket_id}/collect-choice",
        headers={"X-CSRF-Token": str(user["csrfToken"])},
        json={"analysed": True},
    )
    assert chosen.status_code == 200
    return ticket_id


async def _work_leg(
    client: AsyncClient,
    app: FastAPI,
    ticket_id: str,
    manager_username: str,
    draft_title: str,
) -> None:
    """Assign, draft, complete and manager-approve one leg of the ticket."""
    analyst_user = app.state.access_services.repository.get_user_by_username("analyst@example.test")
    assert analyst_user is not None
    manager = await login(client, manager_username)
    assigned = await client.post(
        f"/api/v1/analyst/tasks/{ticket_id}/assign",
        headers={"X-CSRF-Token": str(manager["csrfToken"])},
        json={"analystUserIds": [str(analyst_user.user_id)]},
    )
    assert assigned.status_code == 200
    analyst = await login(client, "analyst@example.test")
    draft = await client.post(
        f"/api/v1/analyst/tasks/{ticket_id}/drafts",
        headers={"X-CSRF-Token": str(analyst["csrfToken"])},
        json=_draft_payload(draft_title),
    )
    assert draft.status_code == 200
    for package in draft.json()["workPackages"]:
        if package["status"] == "complete":
            continue
        completed = await client.patch(
            f"/api/v1/analyst/tasks/{ticket_id}/work-packages/{package['id']}",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json={"status": "complete"},
        )
        assert completed.status_code == 200
    submitted = await client.post(
        f"/api/v1/analyst/tasks/{ticket_id}/submit",
        headers={"X-CSRF-Token": str(analyst["csrfToken"])},
    )
    assert submitted.status_code == 200
    assert submitted.json()["state"] == "MANAGER_APPROVAL"
    manager = await login(client, manager_username)
    approved = await client.post(
        f"/api/v1/routing/{ticket_id}/manager-approval",
        headers={"X-CSRF-Token": str(manager["csrfToken"])},
    )
    assert approved.status_code == 200
    assert approved.json()["state"] == "QC_REVIEW"


async def _qc_approve(client: AsyncClient, app: FastAPI, ticket_id: str) -> Any:
    qc_manager = await login(client, "qc.manager@example.test")
    return await client.post(
        f"/api/v1/qc/products/{ticket_id}/approve",
        headers={"X-CSRF-Token": str(qc_manager["csrfToken"])},
        json=_approval_payload(_acg_id(app, "ACG-EU-CYBER")),
    )


@pytest.mark.asyncio
async def test_qc_forwards_an_analysed_collect_to_rfa_with_the_collect_linked() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _analysed_collect_ticket(client)
        await _work_leg(
            client, app, ticket_id, "collection.manager@example.test", "Raw sensor collect"
        )
        forwarded = await _qc_approve(client, app, ticket_id)
        assert forwarded.status_code == 200
        assert forwarded.json()["state"] == "ANALYST_ASSIGNMENT"

        # The collect stays DRAFT: the customer must not find it in the store.
        await login(client, "user@example.test")
        search = await client.get("/api/v1/store/products?query=Raw%20sensor%20collect")
        assert search.json()["products"] == []
        customer_notifications = await client.get("/api/v1/notifications")
        assert customer_notifications.json()["unread"] == 0

        # The ticket now belongs to the RFA manager's queue on the RFA route.
        await login(client, "rfa.manager@example.test")
        rfa_queue = await client.get("/api/v1/routing/rfa/queue")
        assert ticket_id in [item["ticketId"] for item in rfa_queue.json()["tickets"]]

    ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert ticket is not None
    assert approved_route(ticket) == RoutingRoute.RFA
    assert ticket.collect_disposition == "analysed"
    # The CM leg's assignments were deactivated by the handover.
    assert active_assignments(ticket) == ()
    collect_product_id = ticket.linked_products[-1].product_id
    collect = app.state.store_services.repository.get_product(collect_product_id)
    assert collect is not None
    assert collect.metadata.status == ProductStatus.DRAFT


@pytest.mark.asyncio
async def test_rfa_leg_completes_and_releases_the_assessment_to_the_customer() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _analysed_collect_ticket(client)
        await _work_leg(
            client, app, ticket_id, "collection.manager@example.test", "Leg one collect"
        )
        forwarded = await _qc_approve(client, app, ticket_id)
        assert forwarded.status_code == 200

        # RFA leg: the analyst can see the linked collect while working.
        await _work_leg(
            client, app, ticket_id, "rfa.manager@example.test", "Fused Arctic assessment"
        )
        analyst = await login(client, "analyst@example.test")
        task = await client.get(f"/api/v1/analyst/tasks/{ticket_id}")
        linked_titles = [link["title"] for link in task.json()["linkedProducts"]]
        assert "Leg one collect" in linked_titles
        assert analyst["user"]["username"] == "analyst@example.test"

        released = await _qc_approve(client, app, ticket_id)
        assert released.status_code == 200
        assert released.json()["state"] == "DISSEMINATION_READY"

        await login(client, "user@example.test")
        search = await client.get("/api/v1/store/products?query=Fused%20Arctic")
        assert released.json()["ingestedProduct"]["id"] in {
            product["id"] for product in search.json()["products"]
        }
        notifications = await client.get("/api/v1/notifications")
        assert notifications.json()["unread"] == 1
