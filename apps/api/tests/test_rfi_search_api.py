from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.store import StoreSearchHit
from coeus.domain.tickets import IntakeDetails
from coeus.main import create_app
from coeus.services.rfi_ranking import rank_rfi_hits
from rfi_search_helpers import login, product_payload, submitted_ticket


@pytest.mark.asyncio
async def test_rfi_search_runs_hybrid_ranking_after_access_filtering() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    regional_acg = next(
        acg for acg in app.state.access_services.repository.list_acgs() if "ALPHA" in acg.code
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        admin = await login(client, "admin@example.test")
        created = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
            json=product_payload(str(regional_acg.acg_id), title="Baltic Weather Archive"),
        )
        user = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(client, str(user["csrfToken"]))
        response = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )

    assert created.status_code == 201
    assert response.status_code == 200
    payload = response.json()
    assert payload["ticketState"] == "RFI_MATCH_OFFERED"
    assert payload["offers"][0]["title"] == "Regional Stability Brief"
    assert payload["offers"][0]["offerableToUser"] is True
    assert any("full-text:" in reason for reason in payload["offers"][0]["matchReasons"])
    assert payload["metrics"]["candidateCount"] == 2
    assert "Collection Sensor Summary" not in response.text


@pytest.mark.asyncio
async def test_rfi_search_does_not_leak_unauthorised_counts_or_products() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    collection_product = next(
        product
        for product in app.state.store_services.repository.list_products()
        if product.metadata.title == "Collection Sensor Summary"
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(client, str(user["csrfToken"]))
        run = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )
        results = await client.get(f"/api/v1/rfi-search/{ticket_id}/results")

    assert run.status_code == 200
    assert results.status_code == 200
    assert results.json()["metrics"]["candidateCount"] == 1
    assert str(collection_product.product_id) not in results.text
    assert "Collection Sensor Summary" not in results.text


@pytest.mark.asyncio
async def test_rfi_search_applies_requester_clearance_before_offering() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    regional_acg = next(
        acg for acg in app.state.access_services.repository.list_acgs() if "ALPHA" in acg.code
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        admin = await login(client, "admin@example.test")
        high_side = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
            json=product_payload(
                str(regional_acg.acg_id),
                title="Regional Stability High Side Brief",
                classification=4,
            ),
        )
        user = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(client, str(user["csrfToken"]))
        response = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )

    assert high_side.status_code == 201
    assert response.status_code == 200
    assert "Regional Stability High Side Brief" not in response.text
    assert response.json()["metrics"]["candidateCount"] == 1


@pytest.mark.asyncio
async def test_rfi_search_routes_to_assessment_when_no_offer_exceeds_threshold() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(
            client,
            str(user["csrfToken"]),
            title="Martian Crop Forecast",
            area_or_region="Mars farms",
            output_format="spreadsheet",
        )
        response = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )

    assert response.status_code == 200
    assert response.json()["ticketState"] == "ROUTE_ASSESSMENT"
    assert response.json()["offers"] == []
    assert response.json()["metrics"]["offeredCount"] == 0


@pytest.mark.asyncio
async def test_accepting_product_offer_closes_ticket_and_audits() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(client, str(user["csrfToken"]))
        run = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )
        product_id = run.json()["offers"][0]["productId"]
        accepted = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/offers/{product_id}/accept",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )
        admin = await login(client, "admin@example.test")
        audit = await client.get(
            "/api/v1/audit",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
        )

    assert accepted.status_code == 200
    assert accepted.json()["ticketState"] == "CLOSED_EXISTING_PRODUCT_ACCEPTED"
    assert accepted.json()["offers"][0]["status"] == "accepted"
    assert accepted.json()["metrics"]["acceptedProductId"] == product_id
    assert "product_offer_accepted" in [event["eventType"] for event in audit.json()["events"]]


@pytest.mark.asyncio
async def test_rejecting_last_product_offer_routes_to_assessment() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(client, str(user["csrfToken"]))
        run = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )
        product_id = run.json()["offers"][0]["productId"]
        rejected = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/offers/{product_id}/reject",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={"reason": "Need fresher reporting than this mock brief."},
        )
        manager = await login(client, "collection.manager@example.test")
        manager_results = await client.get(f"/api/v1/rfi-search/{ticket_id}/results")

    assert rejected.status_code == 200
    assert rejected.json()["ticketState"] == "ROUTE_ASSESSMENT"
    assert rejected.json()["offers"][0]["status"] == "rejected"
    assert rejected.json()["offers"][0]["rejectionReason"] == (
        "Need fresher reporting than this mock brief."
    )
    assert rejected.json()["metrics"]["rejectedCount"] == 1
    assert manager["user"]["username"] == "collection.manager@example.test"
    assert manager_results.json()["offers"] == []
    assert manager_results.json()["metrics"]["candidateCount"] == 0


@pytest.mark.asyncio
async def test_rfi_search_denies_invalid_state_and_non_owner_acceptance() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        created = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={"message": "Need something."},
        )
        invalid_run = await client.post(
            f"/api/v1/rfi-search/{created.json()['id']}/run",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )
        ticket_id = await submitted_ticket(client, str(user["csrfToken"]))
        bad_accept_state = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/offers/{uuid4()}/accept",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )
        run = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )
        product_id = run.json()["offers"][0]["productId"]
        admin = await login(client, "admin@example.test")
        denied_accept = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/offers/{product_id}/accept",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
        )

    assert invalid_run.status_code == 409
    assert invalid_run.json()["error"]["code"] == "invalid_ticket_state"
    assert bad_accept_state.status_code == 409
    assert bad_accept_state.json()["error"]["code"] == "invalid_ticket_state"
    assert denied_accept.status_code == 404
    assert denied_accept.json()["error"]["code"] == "ticket_not_found"


@pytest.mark.asyncio
async def test_rfi_search_requires_permission_and_existing_offer() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(client, str(user["csrfToken"]))
        manager = await login(client, "rfa.manager@example.test")
        forbidden = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )
        user = await login(client, "user@example.test")
        run = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )
        missing_offer = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/offers/{uuid4()}/accept",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )

    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"
    assert run.status_code == 200
    assert missing_offer.status_code == 404
    assert missing_offer.json()["error"]["code"] == "product_offer_not_found"


def test_empty_intake_does_not_offer_visible_products() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    product = app.state.store_services.repository.list_products()[0]
    offers = rank_rfi_hits((StoreSearchHit(product, 1.0, ("visible",)),), IntakeDetails())

    assert offers == ()


@pytest.mark.asyncio
async def test_rfi_search_completes_when_queued_agent_run_is_missing() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(client, str(user["csrfToken"]))
        requester = app.state.access_services.repository.get_user_by_username("user@example.test")
        assert requester is not None
        ticket = app.state.ticket_services.tickets.get_visible_ticket(
            requester,
            UUID(ticket_id),
        )
        app.state.ticket_services.tickets.save_system_update(replace(ticket, agent_runs=()))
        response = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )

    assert response.status_code == 200
    assert response.json()["metrics"]["runId"]
