from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName
from coeus.domain.enums import TicketState
from coeus.domain.jioc_routing import JiocRoutingDecision
from coeus.domain.rbac import ROLE_DEFINITIONS
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.main import create_app
from rfi_search_helpers import login


def test_jioc_roles_have_distinct_defaults_and_authority() -> None:
    member = ROLE_DEFINITIONS[RoleName.JIOC_TEAM_MEMBER]
    manager = ROLE_DEFINITIONS[RoleName.JIOC_MANAGER]

    assert member.default_route == "/jioc/queue"
    assert manager.default_route == "/jioc/oversight"
    assert {
        Permission.JIOC_REVIEW,
        Permission.JIOC_RESOLVE_CUSTOMER_DISPUTE,
    } <= member.permissions
    assert {
        Permission.JIOC_REVIEW,
        Permission.JIOC_RESOLVE_CUSTOMER_DISPUTE,
        Permission.JIOC_OVERSIGHT,
        Permission.JIOC_INTERVENE,
        Permission.ANALYTICS_VIEW_GLOBAL,
    } <= manager.permissions
    assert Permission.JIOC_OVERSIGHT not in member.permissions
    assert Permission.JIOC_INTERVENE not in member.permissions
    assert Permission.AUDIT_READ not in manager.permissions


@pytest.mark.asyncio
async def test_seeded_team_member_can_review_but_cannot_oversee_or_intervene() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "jioc.member@example.test")
        queue = await client.get("/api/v1/routing/jioc/queue")
        oversight = await client.get("/api/v1/routing/oversight")
        intervention = await client.post(
            f"/api/v1/routing/{uuid4()}/intervene",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={
                "action": "hold",
                "expectedUpdatedAt": "2026-07-23T09:00:00Z",
                "reason": "Synthetic role-boundary check.",
            },
        )

    assert session["user"]["defaultRoute"] == "/jioc/queue"
    assert "jioc:review" in session["user"]["permissions"]
    assert "jioc:oversight" not in session["user"]["permissions"]
    assert queue.status_code == 200
    assert oversight.status_code == 403
    assert intervention.status_code == 403


@pytest.mark.asyncio
async def test_oversight_exposes_agent_policy_evidence_without_protected_content() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    requester = app.state.access_services.repository.get_user_by_username("user@example.test")
    assert requester is not None
    ticket_id = uuid4()
    context_id = uuid4()
    decision = JiocRoutingDecision(
        decision_id=uuid4(),
        ticket_id=ticket_id,
        context_id=context_id,
        recommended_route="rfa",
        disposition="manager_review",
        confidence=0.42,
        rationale_codes=("risk_review_required",),
        required_clarifications=(),
        policy_version="jioc-routing-policy-v2",
        created_at=datetime.now(UTC),
        evidence_outcome="eligible_rfa",
    )
    app.state.ticket_services.tickets._repository.save(
        TicketRecord(
            ticket_id,
            "TCK-OVERSIGHT-EVIDENCE",
            requester.user_id,
            TicketState.JIOC_REVIEW,
            IntakeDetails(title="Synthetic protected routing requirement"),
            jioc_routing_decisions=(decision,),
        )
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "jioc.team@example.test")
        response = await client.get("/api/v1/routing/oversight")

    assert response.status_code == 200
    body = response.json()
    assert body["countsByAgentDisposition"] == [{"key": "manager_review", "count": 1}]
    task = next(item for item in body["tasks"] if item["ticketId"] == str(ticket_id))
    assert task["agentRoute"] == "rfa"
    assert task["agentRationaleCodes"] == ["risk_review_required"]
    assert task["agentPolicyVersion"] == "jioc-routing-policy-v2"
    assert not ({"intake", "messages", "requiredClarifications"} & set(task))
