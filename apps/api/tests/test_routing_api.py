import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login
from routing_helpers import route_assessment_ticket


@pytest.mark.asyncio
async def test_jioc_runs_capability_reviews_and_keeps_the_decision_human() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await route_assessment_ticket(
            client,
            str(user["csrfToken"]),
            title="Arctic Fisheries Assessment",
            area_or_region="Arctic fisheries",
            output_format="assessment report",
        )
        jioc = await login(client, "jioc.team@example.test")
        queue = await client.get("/api/v1/routing/jioc/queue")
        routed = await client.post(
            f"/api/v1/routing/{ticket_id}/run",
            headers={"X-CSRF-Token": str(jioc["csrfToken"])},
        )

    assert queue.status_code == 200
    assert queue.json()["tickets"][0]["state"] == "JIOC_REVIEW"
    assert routed.status_code == 200
    # The agents only advise: the ticket stays with JIOC for a human decision.
    assert routed.json()["state"] == "JIOC_REVIEW"
    assert routed.json()["recommendation"]["recommendedRoute"] == "rfa"
    assert routed.json()["rfaReview"]["canSatisfy"] is True
    assert routed.json()["rfaReview"]["suggestedTeamName"] == "Maritime Assessment Cell"
    # No genuine collection term in this intake: a team-keyword match alone
    # must not claim the CM route can satisfy the request.
    assert routed.json()["cmReview"]["canSatisfy"] is False
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
        await login(client, "jioc.team@example.test")
        catalogue = await client.get("/api/v1/routing/capability-catalogue")
        await login(client, "rfa.manager@example.test")
        manager_view = await client.get("/api/v1/routing/capability-catalogue")
        await login(client, "user@example.test")
        forbidden = await client.get("/api/v1/routing/capability-catalogue")

    assert catalogue.status_code == 200
    teams = catalogue.json()["teams"]
    assert len([team for team in teams if team["department"] == "rfa"]) >= 10
    assert len([team for team in teams if team["department"] == "cm"]) >= 20
    assert "Maritime Assessment Cell" in {team["name"] for team in teams}
    assert "Cyber Sensor Coordination Cell" in {team["name"] for team in teams}
    assert manager_view.status_code == 200
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_collection_recommendation_surfaces_specialist_candidates() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await route_assessment_ticket(
            client,
            str(user["csrfToken"]),
            title="Arctic Sensor Collection",
            area_or_region="Arctic fisheries",
            output_format="collection plan",
        )
        jioc = await login(client, "jioc.team@example.test")
        routed = await client.post(
            f"/api/v1/routing/{ticket_id}/run",
            headers={"X-CSRF-Token": str(jioc["csrfToken"])},
        )

    assert routed.status_code == 200
    assert routed.json()["state"] == "JIOC_REVIEW"
    assert routed.json()["recommendation"]["recommendedRoute"] == "cm"
    assert routed.json()["rfaReview"]["canSatisfy"] is False
    assert routed.json()["cmReview"]["canSatisfy"] is True
    # The declared IMINT discipline and Arctic region steer the recommendation
    # to the specialist cell instead of the triage fallback.
    assert routed.json()["cmReview"]["suggestedCollectionTeamName"] == (
        "Maritime Imagery Collection Cell"
    )
    candidates = routed.json()["cmReview"]["candidateTeams"]
    assert candidates and candidates[0]["name"] == "Maritime Imagery Collection Cell"
    assert any(reason.startswith("capability:") for reason in candidates[0]["reasons"])


@pytest.mark.asyncio
async def test_clarification_recommendation_pauses_for_the_customer() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await route_assessment_ticket(
            client,
            str(user["csrfToken"]),
            title="Martian Crop Forecast",
            area_or_region="Mars farms",
            output_format="spreadsheet",
        )
        jioc = await login(client, "jioc.team@example.test")
        routed = await client.post(
            f"/api/v1/routing/{ticket_id}/run",
            headers={"X-CSRF-Token": str(jioc["csrfToken"])},
        )
        user = await login(client, "user@example.test")
        ticket = await client.get(f"/api/v1/tickets/{ticket_id}")
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
    ticket_payload = ticket.json()
    assert ticket_payload["messages"][-1]["author"] == "assistant"
    assert "Confirm a supported mock region" in ticket_payload["messages"][-1]["body"]
    assert resumed.status_code == 200
    assert resumed.json()["state"] == "JIOC_REVIEW"


@pytest.mark.asyncio
async def test_jioc_clarification_is_handed_to_customer_chatbot() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await route_assessment_ticket(client, str(user["csrfToken"]))
        jioc = await login(client, "jioc.team@example.test")
        await client.post(
            f"/api/v1/routing/{ticket_id}/run",
            headers={"X-CSRF-Token": str(jioc["csrfToken"])},
        )
        clarification = await client.post(
            f"/api/v1/routing/{ticket_id}/clarification",
            headers={"X-CSRF-Token": str(jioc["csrfToken"])},
            json={
                "route": "rfa",
                "reason": "Scope needs tightening before analyst assignment.",
                "questions": ["Which mock port should take priority?"],
            },
        )
        await login(client, "user@example.test")
        ticket = await client.get(f"/api/v1/tickets/{ticket_id}")

    assert clarification.status_code == 200
    assert clarification.json()["state"] == "INFO_REQUIRED"
    assert clarification.json()["clarifications"][0]["questions"] == [
        "Which mock port should take priority?"
    ]
    ticket_payload = ticket.json()
    assert ticket_payload["messages"][-1]["author"] == "assistant"
    assert "Scope needs tightening" in ticket_payload["messages"][-1]["body"]
    assert "Which mock port should take priority?" in ticket_payload["messages"][-1]["body"]
    assert ticket_payload["timeline"][-1]["eventType"] == "customer_clarification_sent"


@pytest.mark.asyncio
async def test_jioc_approval_to_rfa_moves_to_analyst_assignment() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await route_assessment_ticket(
            client,
            str(user["csrfToken"]),
            title="Arctic Fisheries Assessment",
            area_or_region="Arctic fisheries",
            output_format="assessment report",
        )
        jioc = await login(client, "jioc.team@example.test")
        await client.post(
            f"/api/v1/routing/{ticket_id}/run",
            headers={"X-CSRF-Token": str(jioc["csrfToken"])},
        )
        approved = await client.post(
            f"/api/v1/routing/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(jioc["csrfToken"])},
            json={"route": "rfa"},
        )
        await login(client, "rfa.manager@example.test")
        manager_queue = await client.get("/api/v1/routing/rfa/queue")
        admin = await login(client, "admin@example.test")
        audit = await client.get("/api/v1/audit")

    assert approved.status_code == 200
    assert approved.json()["state"] == "ANALYST_ASSIGNMENT"
    assert approved.json()["managerDecisions"][0]["status"] == "approved"
    assert approved.json()["workflowPlanUpdates"][-1]["title"] == "Prepare analyst assignment"
    # The owning team manager now sees the ticket in their team queue.
    assert manager_queue.status_code == 200
    assert ticket_id in [item["ticketId"] for item in manager_queue.json()["tickets"]]
    assert "route_approved" in [event["eventType"] for event in audit.json()["events"]]
    assert admin["user"]["username"] == "admin@example.test"


@pytest.mark.asyncio
async def test_off_recommendation_approval_requires_reason_and_is_audited() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await route_assessment_ticket(
            client,
            str(user["csrfToken"]),
            title="Arctic Sensor Collection",
            area_or_region="Arctic fisheries",
            output_format="collection plan",
        )
        jioc = await login(client, "jioc.team@example.test")
        await client.post(
            f"/api/v1/routing/{ticket_id}/run",
            headers={"X-CSRF-Token": str(jioc["csrfToken"])},
        )
        missing_reason = await client.post(
            f"/api/v1/routing/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(jioc["csrfToken"])},
            json={"route": "rfa"},
        )
        override = await client.post(
            f"/api/v1/routing/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(jioc["csrfToken"])},
            json={"route": "rfa", "overrideReason": "JIOC accepts assessment-led risk."},
        )
        admin = await login(client, "admin@example.test")
        audit = await client.get("/api/v1/audit")

    assert missing_reason.status_code == 422
    assert missing_reason.json()["error"]["code"] == "override_reason_required"
    assert override.status_code == 200
    assert override.json()["state"] == "ANALYST_ASSIGNMENT"
    assert override.json()["managerDecisions"][0]["overrideReason"] == (
        "JIOC accepts assessment-led risk."
    )
    assert "manager_override" in [event["eventType"] for event in audit.json()["events"]]
    assert admin["user"]["username"] == "admin@example.test"


@pytest.mark.asyncio
async def test_customers_and_managers_cannot_take_jioc_actions() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await route_assessment_ticket(client, str(user["csrfToken"]))
        customer_queue = await client.get("/api/v1/routing/jioc/queue")
        customer_run = await client.post(
            f"/api/v1/routing/{ticket_id}/run",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )
        manager = await login(client, "rfa.manager@example.test")
        manager_run = await client.post(
            f"/api/v1/routing/{ticket_id}/run",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )
        manager_jioc_queue = await client.get("/api/v1/routing/jioc/queue")

    assert customer_queue.status_code == 403
    assert customer_run.status_code == 403
    # Managers lead teams; route decisions belong to JIOC.
    assert manager_run.status_code == 403
    assert manager_jioc_queue.status_code == 403
