from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login
from test_qc_api import _acg_id, _approval_payload, _submitted_qc_ticket


@pytest.mark.asyncio
async def test_customer_accepts_released_product_and_closes_requirement() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id, _ = await _released_ticket(client, app, "Accepted external product")
        customer = await login(client, "user@example.test")
        accepted = await client.post(
            f"/api/v1/tickets/{ticket_id}/requirement-decision",
            headers={"X-CSRF-Token": str(customer["csrfToken"])},
            json={
                "meetsRequirement": True,
                "reason": "The released product meets the requirement.",
                "unmetCriteria": [],
            },
        )
        repeated = await client.post(
            f"/api/v1/tickets/{ticket_id}/requirement-decision",
            headers={"X-CSRF-Token": str(customer["csrfToken"])},
            json={"meetsRequirement": True, "reason": "Confirmed.", "unmetCriteria": []},
        )

    assert accepted.status_code == 200
    assert accepted.json()["state"] == "CLOSED_REQUIREMENT_MET"
    assert accepted.json()["timeline"][-1]["eventType"] == "accepted"
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "invalid_ticket_state"


@pytest.mark.asyncio
async def test_customer_rejection_can_be_referred_and_closed_by_independent_jioc() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id, product_id = await _released_ticket(client, app, "Escalated external product")
        customer = await login(client, "user@example.test")
        rejected = await client.post(
            f"/api/v1/tickets/{ticket_id}/requirement-decision",
            headers={"X-CSRF-Token": str(customer["csrfToken"])},
            json={
                "meetsRequirement": False,
                "reason": "The July coverage does not include the eastern sector.",
                "unmetCriteria": ["July coverage", "Eastern sector"],
            },
        )
        manager = await login(client, "rfa.manager@example.test")
        manager_queue = await client.get("/api/v1/routing/rfa/queue")
        referred = await client.post(
            f"/api/v1/routing/{ticket_id}/reanalysis-manager-decision",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={
                "decision": "refer_to_jioc",
                "rationale": "The published evidence already covers the agreed scope.",
            },
        )
        jioc = await login(client, "jioc.team@example.test")
        jioc_queue = await client.get("/api/v1/routing/jioc/queue")
        closed = await client.post(
            f"/api/v1/routing/{ticket_id}/jioc-reanalysis-decision",
            headers={"X-CSRF-Token": str(jioc["csrfToken"])},
            json={
                "decision": "close",
                "rationale": "The delivered product satisfied the approved requirement.",
            },
        )

    assert rejected.status_code == 200
    assert rejected.json()["state"] == "MANAGER_REANALYSIS_REVIEW"
    queue_ticket = next(
        item for item in manager_queue.json()["tickets"] if item["ticketId"] == ticket_id
    )
    assert queue_ticket["reanalysisContext"]["customerReason"].startswith("The July")
    assert referred.status_code == 200
    assert referred.json()["state"] == "JIOC_REANALYSIS_ADJUDICATION"
    assert referred.json()["reanalysisContext"]["productId"] == product_id
    assert any(item["ticketId"] == ticket_id for item in jioc_queue.json()["tickets"])
    assert closed.status_code == 200
    assert closed.json()["state"] == "CLOSED_REANALYSIS_DECLINED"


@pytest.mark.asyncio
async def test_manager_agreement_starts_a_new_analysis_cycle() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id, _ = await _released_ticket(client, app, "Re-analysis external product")
        customer = await login(client, "user@example.test")
        await client.post(
            f"/api/v1/tickets/{ticket_id}/requirement-decision",
            headers={"X-CSRF-Token": str(customer["csrfToken"])},
            json={
                "meetsRequirement": False,
                "reason": "The output omits one of the agreed synthetic indicators.",
                "unmetCriteria": ["Synthetic indicator"],
            },
        )
        manager = await login(client, "rfa.manager@example.test")
        agreed = await client.post(
            f"/api/v1/routing/{ticket_id}/reanalysis-manager-decision",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={
                "decision": "agree",
                "rationale": "The omitted indicator requires a revised assessment.",
            },
        )

    stored = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert agreed.status_code == 200
    assert agreed.json()["state"] == "ANALYST_IN_PROGRESS"
    assert stored is not None
    assert stored.manager_approved_manifest_hash is None
    assert stored.qc_reviewer_user_id is None
    assert all(package.status.value == "pending" for package in stored.work_packages)


async def _released_ticket(client: AsyncClient, app, title: str) -> tuple[str, str]:
    ticket_id = await _submitted_qc_ticket(client, app, title)
    qc = await login(client, "qc.manager@example.test")
    released = await client.post(
        f"/api/v1/qc/products/{ticket_id}/approve",
        headers={"X-CSRF-Token": str(qc["csrfToken"])},
        json=_approval_payload(_acg_id(app, "ACG-EU-CYBER")),
    )
    assert released.status_code == 200
    return ticket_id, str(released.json()["ingestedProduct"]["id"])
