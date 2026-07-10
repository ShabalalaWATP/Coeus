from dataclasses import replace
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.enums import TicketState
from coeus.domain.tickets import CmCapabilityReview, RfaCapabilityReview, RoutingRoute, TicketRecord
from coeus.main import create_app
from coeus.services.routing_records import recommend_route
from rfi_search_helpers import login
from test_routing_api import _route_assessment_ticket


@pytest.mark.asyncio
async def test_cross_queue_override_is_rejected() -> None:
    """A reviewer without the current queue's permission cannot approve, even
    with an override reason for a route they are allowed to review."""
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
        routed = await client.post(
            f"/api/v1/routing/{ticket_id}/run",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )
    assert routed.status_code == 200
    assert routed.json()["state"] == "RFA_MANAGER_REVIEW"

    collection_manager = app.state.access_services.repository.get_user_by_username(
        "collection.manager@example.test"
    )
    assert collection_manager is not None
    # Broad read access must not grant decision rights in another queue.
    cross_queue_actor = replace(
        collection_manager,
        permissions=collection_manager.permissions | {Permission.TICKET_READ_ALL},
    )
    with pytest.raises(AppError) as exc_info:
        app.state.routing_service.approve(
            cross_queue_actor,
            UUID(ticket_id),
            RoutingRoute.CM,
            "Collection wants this work.",
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "forbidden"


@pytest.mark.asyncio
async def test_same_queue_manager_can_override_to_other_route_with_reason() -> None:
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
        routed = await client.post(
            f"/api/v1/routing/{ticket_id}/run",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )
        missing_reason = await client.post(
            f"/api/v1/routing/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"route": "cm"},
        )
        override = await client.post(
            f"/api/v1/routing/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"route": "cm", "overrideReason": "Collection coverage is more suitable."},
        )

    assert routed.json()["state"] == "RFA_MANAGER_REVIEW"
    assert missing_reason.status_code == 422
    assert missing_reason.json()["error"]["code"] == "override_reason_required"
    assert override.status_code == 200
    assert override.json()["state"] == "ANALYST_ASSIGNMENT"
    assert override.json()["managerDecisions"][-1]["route"] == "cm"


@pytest.mark.asyncio
async def test_route_reviews_roll_back_when_audit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await _route_assessment_ticket(client, str(user["csrfToken"]))
        manager = await login(client, "rfa.manager@example.test")
        monkeypatch.setattr(app.state.routing_service._audit_log, "record", _fail_audit)
        with pytest.raises(RuntimeError, match="audit unavailable"):
            await client.post(
                f"/api/v1/routing/{ticket_id}/run",
                headers={"X-CSRF-Token": str(manager["csrfToken"])},
            )

    ticket = _stored_ticket(app, ticket_id)
    assert ticket.state == TicketState.ROUTE_ASSESSMENT
    assert ticket.rfa_reviews == ()
    assert ticket.cm_reviews == ()
    assert ticket.route_recommendations == ()


@pytest.mark.asyncio
async def test_route_approval_rolls_back_when_audit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        monkeypatch.setattr(app.state.routing_service._audit_log, "record", _fail_audit)
        with pytest.raises(RuntimeError, match="audit unavailable"):
            await client.post(
                f"/api/v1/routing/{ticket_id}/approve",
                headers={"X-CSRF-Token": str(manager["csrfToken"])},
                json={"route": "rfa"},
            )

    ticket = _stored_ticket(app, ticket_id)
    assert ticket.state == TicketState.RFA_MANAGER_REVIEW
    assert ticket.manager_decisions == ()


@pytest.mark.asyncio
async def test_route_rejection_rolls_back_when_audit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        monkeypatch.setattr(app.state.routing_service._audit_log, "record", _fail_audit)
        with pytest.raises(RuntimeError, match="audit unavailable"):
            await client.post(
                f"/api/v1/routing/{ticket_id}/reject",
                headers={"X-CSRF-Token": str(manager["csrfToken"])},
                json={"route": "rfa", "reason": "Not enough scope."},
            )

    ticket = _stored_ticket(app, ticket_id)
    assert ticket.state == TicketState.RFA_MANAGER_REVIEW
    assert ticket.manager_decisions == ()


@pytest.mark.asyncio
async def test_route_clarification_rolls_back_when_audit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        monkeypatch.setattr(app.state.routing_service._audit_log, "record", _fail_audit)
        with pytest.raises(RuntimeError, match="audit unavailable"):
            await client.post(
                f"/api/v1/routing/{ticket_id}/clarification",
                headers={"X-CSRF-Token": str(manager["csrfToken"])},
                json={
                    "route": "rfa",
                    "reason": "Need clearer scope.",
                    "questions": ["Which mock port should take priority?"],
                },
            )

    ticket = _stored_ticket(app, ticket_id)
    assert ticket.state == TicketState.RFA_MANAGER_REVIEW
    assert ticket.manager_decisions == ()
    assert ticket.clarification_requests == ()


def test_recommendation_follows_can_satisfy_without_confidence_gate() -> None:
    ticket_id = uuid4()
    rfa_review = RfaCapabilityReview(
        review_id=uuid4(),
        ticket_id=ticket_id,
        can_satisfy=True,
        confidence=0.4,
        required_clarifications=(),
        suggested_work_packages=(),
        suggested_team_id=None,
        estimated_effort="low",
        risks=(),
        manager_review_required=True,
        reasoning_summary="Assessment can satisfy the request.",
        created_at=datetime.now(UTC),
    )
    cm_review = CmCapabilityReview(
        review_id=uuid4(),
        ticket_id=ticket_id,
        can_satisfy=True,
        confidence=0.9,
        required_clarifications=(),
        suggested_collection_route=None,
        suggested_collection_sources=(),
        estimated_effort="low",
        risks=(),
        manager_review_required=True,
        reasoning_summary="Collection can satisfy the request.",
        created_at=datetime.now(UTC),
    )

    recommendation = recommend_route(ticket_id, rfa_review, cm_review)

    assert recommendation.recommended_route == RoutingRoute.RFA


def _fail_audit(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("audit unavailable")


def _stored_ticket(app: FastAPI, ticket_id: str) -> TicketRecord:
    ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert ticket is not None
    return cast(TicketRecord, ticket)
