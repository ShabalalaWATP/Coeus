from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from coeus.core.config import Settings
from coeus.domain.enums import TicketState
from coeus.domain.jioc_routing import ROUTING_RELEASE, RoutingOperationalSnapshot
from coeus.domain.search_metrics import RfiSearchMetrics
from coeus.domain.tickets import (
    IntakeDetails,
    RoutingRoute,
    TicketRecord,
)
from coeus.main import create_app
from coeus.services.jioc_routing_context import (
    build_routing_context as _context,
)
from coeus.services.jioc_routing_context import (
    evidence_failures as _evidence_failures,
)
from coeus.services.jioc_routing_policy import decide as _decide
from coeus.services.ticket_records import timeline
from jioc_test_helpers import cm_review as _cm_review
from jioc_test_helpers import rfa_review as _rfa_review
from rfi_search_helpers import login, submitted_ticket


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("output_format", "description", "expected_state", "expected_route"),
    [
        ("assessment report", "Assess the available reporting.", "ANALYST_ASSIGNMENT", "rfa"),
        ("collection plan", "Monitor the area with sensors.", "COLLECT_CHOICE", "cm"),
    ],
)
async def test_jioc_agent_auto_applies_routine_routes(
    output_format: str,
    description: str,
    expected_state: str,
    expected_route: str,
) -> None:
    app = create_app(_settings())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(
            client,
            str(session["csrfToken"]),
            title="Synthetic routing requirement",
            area_or_region="Baltic ports",
            output_format=output_format,
        )

    prepared = _prepare(app, ticket_id, description=description)
    result = app.state.jioc_routing_agent_service.route(prepared.ticket_id)

    assert result.state.value == expected_state
    assert result.jioc_routing_decisions[-1].recommended_route == expected_route
    assert result.jioc_routing_decisions[-1].disposition == "auto_applied"
    assert result.jioc_routing_contexts[-1].search_assurance == "definitive"
    assert result.rfa_reviews[-1].manager_review_required is False
    assert result.cm_reviews[-1].manager_review_required is False


@pytest.mark.asyncio
async def test_jioc_agent_escalates_risk_to_manager_on_the_loop() -> None:
    app = create_app(_settings())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(
            client,
            str(session["csrfToken"]),
            title="Synthetic restricted assessment",
            area_or_region="Baltic ports",
        )

    prepared = _prepare(
        app,
        ticket_id,
        description="Assess the available reporting.",
        restrictions="Special handling needs a human decision.",
    )
    result = app.state.jioc_routing_agent_service.route(prepared.ticket_id)

    assert result.state == TicketState.JIOC_REVIEW
    assert result.jioc_routing_decisions[-1].disposition == "manager_review"
    assert result.jioc_routing_decisions[-1].rationale_codes == ("risk_review_required",)
    assert result.rfa_reviews[-1].manager_review_required is True


@pytest.mark.asyncio
async def test_jioc_agent_escalates_conflicting_capability_recommendations() -> None:
    app = create_app(_settings())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(
            client,
            str(session["csrfToken"]),
            title="Synthetic dual capability request",
            area_or_region="Baltic ports",
        )
    prepared = _prepare(app, ticket_id, description="Assess and collect reporting.")
    app.state.jioc_routing_agent_service._rfa_agent.review = lambda _ticket: _rfa_review(
        prepared.ticket_id, True, 0.90
    )
    app.state.jioc_routing_agent_service._cm_agent.review = lambda _ticket: _cm_review(
        prepared.ticket_id, True, 0.95
    )

    result = app.state.jioc_routing_agent_service.route(prepared.ticket_id)

    assert result.state == TicketState.JIOC_REVIEW
    assert result.route_recommendations[-1].recommended_route == RoutingRoute.CM
    assert result.jioc_routing_decisions[-1].rationale_codes == ("conflicting_route_signals",)


def test_jioc_agent_handles_missing_stale_and_low_confidence_inputs() -> None:
    app = create_app(_settings())
    service = app.state.jioc_routing_agent_service
    with pytest.raises(LookupError, match="not found"):
        service.route(uuid4())

    actor = app.state.access_services.repository.get_user_by_username("user@example.test")
    assert actor is not None
    draft = TicketRecord(
        uuid4(),
        "RFI-STALE-ROUTE",
        actor.user_id,
        TicketState.DRAFT_INTAKE,
        IntakeDetails(title="Synthetic stale route", operational_question="What changed?"),
    )
    app.state.ticket_services.tickets.save_system_update(draft)
    unchanged = service.route(draft.ticket_id)
    assert unchanged.ticket_id == draft.ticket_id
    assert unchanged.state == TicketState.DRAFT_INTAKE

    now = datetime.now(UTC)
    context = _context(
        replace(
            draft,
            state=TicketState.JIOC_ROUTING_PENDING,
            timeline=(
                timeline(
                    draft.ticket_id,
                    actor.user_id,
                    "active_work_search_completed",
                    "No matching work found.",
                ),
            ),
        ),
        RoutingOperationalSnapshot("capability-catalogue-v1", now, ()),
        now,
    )
    disposition = _decide(
        draft,
        replace(
            context,
            search_assurance="definitive",
            search_coverage="complete",
            active_work_search_completed=True,
        ),
        _rfa_review(draft.ticket_id, False, 0.20),
        _cm_review(draft.ticket_id, False, 0.30),
    )
    assert disposition[:2] == ("manager_review", RoutingRoute.CLARIFICATION)

    failures = _evidence_failures(
        SimpleNamespace(
            search_assurance="assisted",
            search_coverage="partial",
            product_offer_statuses=(f"{uuid4()}:offered",),
            active_work_search_completed=False,
            active_work_offer_statuses=(f"{uuid4()}:offered",),
            capability_catalogue_version="capability-catalogue-v1",
            availability_snapshot_at=now,
            created_at=now,
            capacity_freshness_seconds=300,
        ),
    )
    assert failures == (
        "product_search_not_definitive",
        "product_offer_unresolved",
        "active_work_search_missing",
        "active_work_offer_unresolved",
    )


@pytest.mark.asyncio
async def test_jioc_manager_can_hold_resume_and_reopen_an_automatic_route() -> None:
    app = create_app(_settings())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        customer = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(
            client,
            str(customer["csrfToken"]),
            title="Synthetic intervention requirement",
            area_or_region="Baltic ports",
        )
        prepared = _prepare(app, ticket_id, description="Assess the available reporting.")
        app.state.jioc_routing_agent_service.route(prepared.ticket_id)
        manager = await login(client, "jioc.team@example.test")
        hold = await _intervene(client, ticket_id, str(manager["csrfToken"]), "hold")
        resume = await _intervene(client, ticket_id, str(manager["csrfToken"]), "resume")
        review = await _intervene(client, ticket_id, str(manager["csrfToken"]), "send_to_review")

    assert hold.json()["state"] == "JIOC_INTERVENTION_HOLD"
    assert resume.json()["state"] == "ANALYST_ASSIGNMENT"
    assert review.json()["state"] == "JIOC_REVIEW"
    stored = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert stored is not None
    assert [item.action for item in stored.jioc_interventions] == [
        "hold",
        "resume",
        "send_to_review",
    ]


@pytest.mark.asyncio
async def test_jioc_intervention_rejects_unauthorised_missing_and_invalid_work() -> None:
    app = create_app(_settings())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        customer = await login(client, "user@example.test")
        created = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": str(customer["csrfToken"])},
            json={"message": "Need a synthetic oversight test request."},
        )
        ticket_id = created.json()["id"]
        forbidden = await client.post(
            f"/api/v1/routing/{ticket_id}/intervene",
            headers={"X-CSRF-Token": str(customer["csrfToken"])},
            json={"action": "hold", "reason": "Synthetic unauthorised intervention."},
        )
        manager = await login(client, "jioc.team@example.test")
        missing = await client.post(
            f"/api/v1/routing/{uuid4()}/intervene",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"action": "hold", "reason": "Synthetic missing request."},
        )
        invalid = {}
        for action in ("hold", "resume", "send_to_review"):
            response = await client.post(
                f"/api/v1/routing/{ticket_id}/intervene",
                headers={"X-CSRF-Token": str(manager["csrfToken"])},
                json={"action": action, "reason": "Synthetic invalid state."},
            )
            invalid[action] = response.status_code

    assert forbidden.status_code == 403
    assert missing.status_code == 404
    assert invalid == {"hold": 409, "resume": 409, "send_to_review": 409}


async def _intervene(client: AsyncClient, ticket_id: str, csrf_token: str, action: str) -> Response:
    response = await client.post(
        f"/api/v1/routing/{ticket_id}/intervene",
        headers={"X-CSRF-Token": csrf_token},
        json={"action": action, "reason": "Manager oversight test intervention."},
    )
    assert response.status_code == 200
    return response


def _prepare(
    app: FastAPI,
    ticket_id: str,
    *,
    description: str,
    restrictions: str | None = None,
) -> TicketRecord:
    app.state.jioc_routing_agent_service._operational_context = _AvailableOperationalContext()
    ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert ticket is not None
    now = datetime.now(UTC)
    metric = RfiSearchMetrics(
        run_id=uuid4(),
        query="synthetic routing requirement",
        candidate_count=0,
        offered_count=0,
        rejected_count=0,
        accepted_product_id=None,
        created_at=now,
        outcome="no_match",
        assurance="definitive",
        coverage_status="complete",
        corpus_version="test-corpus-v1",
    )
    prepared = replace(
        ticket,
        state=TicketState.JIOC_ROUTING_PENDING,
        intake=replace(
            ticket.intake,
            description=description,
            restrictions_or_caveats=restrictions,
        ),
        product_offers=(),
        active_work_offers=(),
        search_metrics=(metric,),
        timeline=(
            *ticket.timeline,
            timeline(
                ticket.ticket_id,
                ticket.requester_user_id,
                "active_work_search_completed",
                "No matching active work found.",
            ),
        ),
    )
    app.state.ticket_services.tickets.save_system_update(prepared)
    return prepared


def _settings() -> Settings:
    return Settings(
        environment="test",
        argon2_memory_cost=8_192,
        persistence_provider="memory",
        jioc_agent_routing_enabled="active",
        jioc_routing_approved_releases=[ROUTING_RELEASE],
    )


class _AvailableOperationalContext:
    def snapshot(
        self, _ticket: TicketRecord, candidate_team_ids: tuple[str, ...]
    ) -> RoutingOperationalSnapshot:
        return RoutingOperationalSnapshot(
            "capability-catalogue-v1",
            datetime.now(UTC),
            tuple(f"{team_id}:available:1" for team_id in candidate_team_ids),
        )
