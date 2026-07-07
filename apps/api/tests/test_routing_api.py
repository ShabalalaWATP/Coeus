import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login, submitted_ticket


@pytest.mark.asyncio
async def test_routing_runs_rfa_first_capability_review() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await _route_assessment_ticket(
            client,
            str(user["csrfToken"]),
            title="Arctic Fisheries Assessment",
            area_or_region="Arctic fisheries",
            output_format="assessment report",
        )
        manager = await login(client, "rfa.manager@example.test")
        queue = await client.get("/api/v1/routing/rfa/queue")
        routed = await client.post(
            f"/api/v1/routing/{ticket_id}/run",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )

    assert queue.status_code == 200
    assert queue.json()["tickets"][0]["state"] == "ROUTE_ASSESSMENT"
    assert routed.status_code == 200
    assert routed.json()["state"] == "RFA_MANAGER_REVIEW"
    assert routed.json()["recommendation"]["recommendedRoute"] == "rfa"
    assert routed.json()["rfaReview"]["canSatisfy"] is True
    assert routed.json()["rfaReview"]["suggestedTeamName"] == "Maritime Assessment Cell"
    assert routed.json()["cmReview"]["canSatisfy"] is True
    assert routed.json()["agentRuns"][-3:] == [
        "rfa-capability-agent",
        "cm-capability-agent",
        "orchestrator-agent",
    ]


@pytest.mark.asyncio
async def test_capability_catalogue_lists_rfa_and_collection_teams_for_managers() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "rfa.manager@example.test")
        catalogue = await client.get("/api/v1/routing/capability-catalogue")
        await login(client, "user@example.test")
        forbidden = await client.get("/api/v1/routing/capability-catalogue")

    assert catalogue.status_code == 200
    teams = catalogue.json()["teams"]
    assert len([team for team in teams if team["department"] == "rfa"]) >= 10
    assert len([team for team in teams if team["department"] == "cm"]) >= 20
    assert "Maritime Assessment Cell" in {team["name"] for team in teams}
    assert "Cyber Sensor Coordination Cell" in {team["name"] for team in teams}
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_routing_falls_back_to_collection_when_rfa_cannot_satisfy() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await _route_assessment_ticket(
            client,
            str(user["csrfToken"]),
            title="Arctic Sensor Collection",
            area_or_region="Arctic fisheries",
            output_format="collection plan",
        )
        manager = await login(client, "collection.manager@example.test")
        routed = await client.post(
            f"/api/v1/routing/{ticket_id}/run",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )
        queue = await client.get("/api/v1/routing/cm/queue")

    assert routed.status_code == 200
    assert routed.json()["state"] == "CM_MANAGER_REVIEW"
    assert routed.json()["recommendation"]["recommendedRoute"] == "cm"
    assert routed.json()["rfaReview"]["canSatisfy"] is False
    assert routed.json()["cmReview"]["canSatisfy"] is True
    assert routed.json()["cmReview"]["suggestedCollectionTeamName"] == (
        "Collection Coordination Triage Cell"
    )
    assert queue.json()["tickets"][0]["ticketId"] == ticket_id


@pytest.mark.asyncio
async def test_routing_prefers_rfa_when_both_capability_agents_can_satisfy() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await _route_assessment_ticket(
            client,
            str(user["csrfToken"]),
            title="Arctic Imagery Assessment",
            area_or_region="Arctic fisheries",
            output_format="assessment report with imagery collection options",
        )
        manager = await login(client, "rfa.manager@example.test")
        routed = await client.post(
            f"/api/v1/routing/{ticket_id}/run",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )

    assert routed.status_code == 200
    assert routed.json()["state"] == "RFA_MANAGER_REVIEW"
    assert routed.json()["recommendation"]["recommendedRoute"] == "rfa"
    assert routed.json()["rfaReview"]["canSatisfy"] is True
    assert routed.json()["cmReview"]["canSatisfy"] is True


@pytest.mark.asyncio
async def test_routing_requests_clarification_when_neither_route_can_satisfy() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await _route_assessment_ticket(
            client,
            str(user["csrfToken"]),
            title="Martian Crop Forecast",
            area_or_region="Mars farms",
            output_format="spreadsheet",
        )
        manager = await login(client, "rfa.manager@example.test")
        routed = await client.post(
            f"/api/v1/routing/{ticket_id}/run",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )
        user = await login(client, "user@example.test")
        tickets = await client.get("/api/v1/tickets")
        resumed = await client.post(
            f"/api/v1/tickets/{ticket_id}/timeline",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={"body": "Use a supported mock region in the Arctic."},
        )

    assert routed.status_code == 200
    routed_payload = routed.json()
    assert routed_payload["state"] == "INFO_REQUIRED"
    assert routed_payload["recommendation"]["recommendedRoute"] == "clarification"
    assert routed_payload["rfaReview"]["requiredClarifications"]
    assert routed_payload["clarifications"][0]["route"] == "clarification"
    ticket_payload = tickets.json()["tickets"][0]
    assert ticket_payload["messages"][-1]["author"] == "assistant"
    assert "Confirm a supported mock region" in ticket_payload["messages"][-1]["body"]
    assert [run["agentName"] for run in ticket_payload["agentRuns"][-2:]] == [
        "orchestrator-agent",
        "customer-chatbot-agent",
    ]
    assert resumed.status_code == 200
    assert resumed.json()["state"] == "ROUTE_ASSESSMENT"


@pytest.mark.asyncio
async def test_manager_clarification_is_handed_to_customer_chatbot() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await _route_assessment_ticket(client, str(user["csrfToken"]))
        manager = await login(client, "rfa.manager@example.test")
        await client.post(
            f"/api/v1/routing/{ticket_id}/run",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )
        clarification = await client.post(
            f"/api/v1/routing/{ticket_id}/clarification",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={
                "route": "rfa",
                "reason": "Scope needs tightening before analyst assignment.",
                "questions": ["Which mock port should take priority?"],
            },
        )
        await login(client, "user@example.test")
        tickets = await client.get("/api/v1/tickets")

    assert clarification.status_code == 200
    assert clarification.json()["state"] == "INFO_REQUIRED"
    assert clarification.json()["clarifications"][0]["questions"] == [
        "Which mock port should take priority?"
    ]
    ticket_payload = tickets.json()["tickets"][0]
    assert ticket_payload["messages"][-1]["author"] == "assistant"
    assert "Scope needs tightening" in ticket_payload["messages"][-1]["body"]
    assert "Which mock port should take priority?" in ticket_payload["messages"][-1]["body"]
    assert ticket_payload["timeline"][-1]["eventType"] == "customer_clarification_sent"


@pytest.mark.asyncio
async def test_rfa_manager_approval_updates_project_plan_and_audit_log() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await _route_assessment_ticket(
            client,
            str(user["csrfToken"]),
            title="Arctic Fisheries Assessment",
            area_or_region="Arctic fisheries",
            output_format="assessment report",
        )
        manager = await login(client, "rfa.manager@example.test")
        await client.post(
            f"/api/v1/routing/{ticket_id}/run",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )
        approved = await client.post(
            f"/api/v1/routing/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"route": "rfa"},
        )
        admin = await login(client, "admin@example.test")
        audit = await client.get("/api/v1/audit")

    assert approved.status_code == 200
    assert approved.json()["state"] == "ANALYST_ASSIGNMENT"
    assert approved.json()["managerDecisions"][0]["status"] == "approved"
    assert approved.json()["projectPlanUpdates"][-1]["title"] == "Prepare analyst assignment"
    assert "route_approved" in [event["eventType"] for event in audit.json()["events"]]
    assert admin["user"]["username"] == "admin@example.test"


@pytest.mark.asyncio
async def test_admin_override_requires_reason_and_is_audited() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await _route_assessment_ticket(
            client,
            str(user["csrfToken"]),
            title="Arctic Sensor Collection",
            area_or_region="Arctic fisheries",
            output_format="collection plan",
        )
        manager = await login(client, "collection.manager@example.test")
        await client.post(
            f"/api/v1/routing/{ticket_id}/run",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )
        admin = await login(client, "admin@example.test")
        missing_reason = await client.post(
            f"/api/v1/routing/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
            json={"route": "rfa"},
        )
        override = await client.post(
            f"/api/v1/routing/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
            json={"route": "rfa", "overrideReason": "Assessment manager accepts risk."},
        )
        audit = await client.get("/api/v1/audit")

    assert missing_reason.status_code == 422
    assert missing_reason.json()["error"]["code"] == "override_reason_required"
    assert override.status_code == 200
    assert override.json()["managerDecisions"][0]["overrideReason"] == (
        "Assessment manager accepts risk."
    )
    assert "manager_override" in [event["eventType"] for event in audit.json()["events"]]


@pytest.mark.asyncio
async def test_customer_cannot_access_routing_manager_actions() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await _route_assessment_ticket(client, str(user["csrfToken"]))
        queue = await client.get("/api/v1/routing/rfa/queue")
        routed = await client.post(
            f"/api/v1/routing/{ticket_id}/run",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )

    assert queue.status_code == 403
    assert routed.status_code == 403


async def _route_assessment_ticket(
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
