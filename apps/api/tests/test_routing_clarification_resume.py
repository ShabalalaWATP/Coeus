"""Routing-phase INFO_REQUIRED must resume JIOC review, never regress to intake."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.enums import TicketState
from coeus.domain.routing_phase import routing_history_present
from coeus.domain.tickets import (
    ClarificationRequest,
    IntakeDetails,
    ManagerRoutingDecision,
    ManagerRoutingDecisionStatus,
    RoutingRoute,
    TicketRecord,
)
from coeus.main import create_app
from coeus.services.conversation_routing_resume import chat_reply_projection
from rfi_search_helpers import login
from routing_helpers import route_assessment_ticket, routing_version


def _ticket(**overrides: object) -> TicketRecord:
    defaults: dict[str, object] = {
        "ticket_id": uuid4(),
        "reference": "TCK-9001",
        "requester_user_id": uuid4(),
        "state": TicketState.INFO_REQUIRED,
        "intake": IntakeDetails(),
    }
    defaults.update(overrides)
    return TicketRecord(**defaults)  # type: ignore[arg-type]


def _manager_decision(ticket_id: UUID) -> ManagerRoutingDecision:
    return ManagerRoutingDecision(
        decision_id=uuid4(),
        ticket_id=ticket_id,
        route=RoutingRoute.RFA,
        status=ManagerRoutingDecisionStatus.CLARIFICATION_REQUESTED,
        reason="Confirm the reporting window.",
        override_reason=None,
        actor_user_id=uuid4(),
        created_at=datetime.now(UTC),
    )


def test_routing_history_requires_at_least_one_routing_artefact() -> None:
    plain = _ticket()
    assert routing_history_present(plain) is False
    decided = replace(plain, manager_decisions=(_manager_decision(plain.ticket_id),))
    assert routing_history_present(decided) is True
    clarified = replace(
        plain,
        clarification_requests=(
            ClarificationRequest(
                clarification_id=uuid4(),
                ticket_id=plain.ticket_id,
                route=RoutingRoute.CLARIFICATION,
                reason="Confirm the reporting window.",
                questions=("Which week should the assessment cover?",),
                requested_by_user_id=uuid4(),
                created_at=datetime.now(UTC),
            ),
        ),
    )
    assert routing_history_present(clarified) is True


def test_chat_reply_on_routing_clarification_resumes_jioc_review() -> None:
    ticket = _ticket()
    ticket = replace(ticket, manager_decisions=(_manager_decision(ticket.ticket_id),))
    state, entries = chat_reply_projection(
        ticket,
        ticket.requester_user_id,
        ticket.intake,
        (),
        lambda current, intake: TicketState.DRAFT_INTAKE,
    )
    assert state == TicketState.JIOC_REVIEW
    assert entries[-1].event_type == "route_assessment_resumed"


def test_flagged_chat_reply_is_not_treated_as_a_clarification_answer() -> None:
    ticket = _ticket()
    ticket = replace(ticket, manager_decisions=(_manager_decision(ticket.ticket_id),))
    state, entries = chat_reply_projection(
        ticket,
        ticket.requester_user_id,
        ticket.intake,
        ("prompt_injection",),
        lambda current, intake: current,
    )
    assert state == TicketState.INFO_REQUIRED
    assert all(entry.event_type != "route_assessment_resumed" for entry in entries)


def test_intake_phase_chat_reply_keeps_the_intake_state_machine() -> None:
    ticket = _ticket()
    state, entries = chat_reply_projection(
        ticket,
        ticket.requester_user_id,
        ticket.intake,
        (),
        lambda current, intake: TicketState.DRAFT_INTAKE,
    )
    assert state == TicketState.DRAFT_INTAKE
    assert all(entry.event_type != "route_assessment_resumed" for entry in entries)


async def _clarified_ticket_without_recommendations(
    client: AsyncClient, app: object, csrf_token: str
) -> str:
    """Reach INFO_REQUIRED via a manager clarification on a deferred referral."""
    ticket_id = await route_assessment_ticket(client, csrf_token)
    tickets = app.state.ticket_services.tickets  # type: ignore[attr-defined]
    stored = tickets._repository.get(UUID(ticket_id))
    assert stored is not None
    tickets.save_system_update(
        replace(
            stored,
            state=TicketState.JIOC_REVIEW,
            route_recommendations=(),
            jioc_routing_decisions=(),
            manager_decisions=(),
            clarification_requests=(),
        )
    )
    jioc = await login(client, "jioc.team@example.test")
    clarification = await client.post(
        f"/api/v1/routing/{ticket_id}/clarification",
        headers={"X-CSRF-Token": str(jioc["csrfToken"])},
        json={
            "route": "rfa",
            "reason": "Confirm the reporting window.",
            "questions": ["Which week should the assessment cover?"],
            "expectedUpdatedAt": await routing_version(client, ticket_id),
        },
    )
    assert clarification.status_code == 200
    assert clarification.json()["state"] == "INFO_REQUIRED"
    return ticket_id


@pytest.mark.asyncio
async def test_clarification_answer_resumes_review_without_agent_recommendations() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await _clarified_ticket_without_recommendations(
            client, app, str(user["csrfToken"])
        )
        user = await login(client, "user@example.test")
        answered = await client.post(
            f"/api/v1/tickets/{ticket_id}/timeline",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={"body": "Cover the first week of August."},
        )

    assert answered.status_code == 200
    assert answered.json()["state"] == "JIOC_REVIEW"


@pytest.mark.asyncio
async def test_chat_answer_resumes_review_instead_of_regressing_to_draft() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await _clarified_ticket_without_recommendations(
            client, app, str(user["csrfToken"])
        )
        user = await login(client, "user@example.test")
        ticket = await client.get(f"/api/v1/tickets/{ticket_id}")
        if ticket.json().get("conversationStatus") == "closed":
            reopened = await client.post(
                f"/api/v1/tickets/{ticket_id}/conversation/reopen",
                headers={"X-CSRF-Token": str(user["csrfToken"])},
            )
            assert reopened.status_code == 200
        reply = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={
                "ticketId": ticket_id,
                "message": "Cover the first week of August for the mock ports.",
            },
        )

    assert reply.status_code == 201
    payload = reply.json()
    assert payload["state"] == "JIOC_REVIEW"
    events = [entry["eventType"] for entry in payload["timeline"]]
    assert "route_assessment_resumed" in events
