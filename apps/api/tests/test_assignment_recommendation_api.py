"""HTTP and service behaviour for human-reviewed assignment recommendations."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.assignment_recommendations import (
    AcceptRecommendationRequest,
    AssignmentRecommendationAcceptance,
    AssignmentRecommendationConflict,
    AssignmentRecommendationDenied,
    AssignmentRecommendationPreview,
    ExclusionCode,
    PrepareRecommendationRequest,
    RankedAssignmentCandidate,
    RecommendationCode,
)
from coeus.main import create_app
from coeus.services.assignment_recommendations import AssignmentRecommendationService
from rfi_search_helpers import login
from routing_helpers import analyst_assignment_ticket

HASH = "a" * 64
DEADLINE = (datetime.now(UTC) + timedelta(days=3)).isoformat()


class _Store:
    """Records the prepared demand and replays scripted outcomes."""

    def __init__(self, analyst_id: UUID, unit_id: UUID) -> None:
        self.analyst_id = analyst_id
        self.unit_id = unit_id
        self.prepare_error: Exception | None = None
        self.acceptance_error: Exception | None = None
        self.prepared: PrepareRecommendationRequest | None = None
        self.candidates = (
            RankedAssignmentCandidate(
                unit_id, analyst_id, 1, 480, 0, (RecommendationCode.ACTIVE_ACCOUNT,)
            ),
        )

    def prepare(
        self, actor_user_id: UUID, request: PrepareRecommendationRequest
    ) -> AssignmentRecommendationPreview:
        self.prepared = request
        self.actor_user_id = actor_user_id
        if self.prepare_error is not None:
            raise self.prepare_error
        return AssignmentRecommendationPreview(
            uuid4(),
            uuid4(),
            1,
            uuid4(),
            HASH,
            datetime.now(UTC) + timedelta(minutes=15),
            self.candidates,
            ((ExclusionCode.CAPACITY_UNAVAILABLE, 2),),
        )

    def acceptance(
        self, actor_user_id: UUID, request: AcceptRecommendationRequest
    ) -> AssignmentRecommendationAcceptance:
        if self.acceptance_error is not None:
            raise self.acceptance_error
        return AssignmentRecommendationAcceptance(
            request.recommendation_id,
            request.preview_hash,
            actor_user_id,
            request.selected_unit_id,
            request.selected_analyst_user_id,
            request.override_reason,
        )


def _install(app: FastAPI) -> _Store:
    analyst = app.state.access_services.repository.get_user_by_username("analyst@example.test")
    assert analyst is not None
    team = next(
        item
        for item in app.state.team_repository.list_teams()
        if item.name == "RFA Assessment Team"
    )
    store = _Store(analyst.user_id, team.team_id)
    app.state.assignment_recommendation_service = AssignmentRecommendationService(
        app.state.ticket_services, app.state.analyst_assignment_service, store
    )
    return store


def _payload(**overrides: object) -> dict[str, object]:
    return {
        "effortMinMinutes": 240,
        "effortMaxMinutes": 480,
        "deadline": DEADLINE,
        "capabilityIds": ["regional-analysis", " regional-analysis "],
        **overrides,
    }


@pytest.mark.asyncio
async def test_preview_bounds_the_demand_and_names_only_authorised_candidates() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    store = _install(app)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await analyst_assignment_ticket(client)
        manager = await login(client, "rfa.manager@example.test")
        csrf = {"X-CSRF-Token": str(manager["csrfToken"])}

        response = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/assignment-recommendations/preview",
            headers=csrf,
            json=_payload(),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["previewHash"] == HASH
    assert body["exclusionCounts"] == {"capacity_unavailable": 2}
    assert body["candidates"][0]["displayName"]
    assert body["candidates"][0]["explanationCodes"] == ["active_account"]
    assert store.prepared is not None
    # Repeated capabilities are normalised to one entry before the store sees them.
    assert store.prepared.demand.capability_ids == ("regional-analysis",)
    assert store.prepared.unit_id is None


@pytest.mark.asyncio
async def test_preview_accepts_an_explicit_unit_and_refuses_an_unmanaged_one() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    store = _install(app)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await analyst_assignment_ticket(client)
        manager = await login(client, "rfa.manager@example.test")
        csrf = {"X-CSRF-Token": str(manager["csrfToken"])}
        root = f"/api/v1/analyst/tasks/{ticket_id}/assignment-recommendations"

        scoped = await client.post(
            root + "/preview", headers=csrf, json=_payload(unitId=str(store.unit_id))
        )
        unmanaged = await client.post(
            root + "/preview", headers=csrf, json=_payload(unitId=str(uuid4()))
        )

    assert scoped.status_code == 200
    assert store.prepared is not None and store.prepared.unit_id == store.unit_id
    assert unmanaged.status_code == 404
    assert unmanaged.json()["error"]["code"] == "assignment_team_not_found"


@pytest.mark.asyncio
async def test_preview_translates_store_refusals_without_leaking_detail() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    store = _install(app)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await analyst_assignment_ticket(client)
        manager = await login(client, "rfa.manager@example.test")
        csrf = {"X-CSRF-Token": str(manager["csrfToken"])}
        root = f"/api/v1/analyst/tasks/{ticket_id}/assignment-recommendations/preview"

        store.prepare_error = AssignmentRecommendationDenied("cohort is not eligible")
        denied = await client.post(root, headers=csrf, json=_payload())
        store.prepare_error = ValueError("effort is invalid")
        invalid = await client.post(root, headers=csrf, json=_payload())

    assert denied.status_code == 409
    assert denied.json()["error"]["code"] == "assignment_recommendation_unavailable"
    assert "cohort" not in denied.text
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_assignment_demand"


@pytest.mark.asyncio
async def test_a_free_text_ticket_deadline_leaves_the_requested_bound_in_place() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    store = _install(app)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        # The intake helper records a free-text deadline of "Friday".
        ticket_id = await analyst_assignment_ticket(client)
        manager = await login(client, "rfa.manager@example.test")

        response = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/assignment-recommendations/preview",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json=_payload(),
        )

    assert response.status_code == 200
    assert store.prepared is not None
    assert store.prepared.demand.deadline == datetime.fromisoformat(DEADLINE).astimezone(UTC)


@pytest.mark.asyncio
async def test_preview_requires_a_time_zone_on_the_requested_deadline() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    _install(app)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await analyst_assignment_ticket(client)
        manager = await login(client, "rfa.manager@example.test")

        response = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/assignment-recommendations/preview",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json=_payload(deadline="2026-09-01T09:00:00"),
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_deadline"


@pytest.mark.asyncio
async def test_accept_requires_the_relational_transaction_service() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    store = _install(app)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await analyst_assignment_ticket(client)
        manager = await login(client, "rfa.manager@example.test")

        # Acceptance commits ownership and capacity together, so it fails closed
        # rather than assigning without the transactional store.
        response = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/assignment-recommendations/accept",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={
                "recommendationId": str(uuid4()),
                "previewHash": HASH,
                "selectedUnitId": str(store.unit_id),
                "selectedAnalystUserId": str(store.analyst_id),
                "workPackages": ["Assess reporting"],
            },
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "assignment_recommendation_unavailable"


@pytest.mark.asyncio
async def test_accept_translates_conflict_and_ineligibility_separately() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    store = _install(app)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await analyst_assignment_ticket(client)
        manager = await login(client, "rfa.manager@example.test")
        csrf = {"X-CSRF-Token": str(manager["csrfToken"])}
        root = f"/api/v1/analyst/tasks/{ticket_id}/assignment-recommendations/accept"
        body = {
            "recommendationId": str(uuid4()),
            "previewHash": HASH,
            "selectedUnitId": str(store.unit_id),
            "selectedAnalystUserId": str(store.analyst_id),
            "workPackages": ["Assess reporting"],
        }

        store.acceptance_error = AssignmentRecommendationConflict("hash changed")
        conflict = await client.post(root, headers=csrf, json=body)
        store.acceptance_error = AssignmentRecommendationDenied("candidate suspended")
        ineligible = await client.post(root, headers=csrf, json=body)

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "assignment_recommendation_changed"
    assert ineligible.status_code == 409
    assert ineligible.json()["error"]["code"] == "assignment_candidate_ineligible"


@pytest.mark.asyncio
async def test_recommendations_are_unavailable_without_a_configured_service() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await analyst_assignment_ticket(client)
        manager = await login(client, "rfa.manager@example.test")

        response = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/assignment-recommendations/preview",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json=_payload(),
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "assignment_recommendation_unavailable"


@pytest.mark.asyncio
async def test_an_analyst_cannot_preview_or_accept_a_recommendation() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    store = _install(app)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await analyst_assignment_ticket(client)
        analyst = await login(client, "analyst@example.test")
        csrf = {"X-CSRF-Token": str(analyst["csrfToken"])}
        root = f"/api/v1/analyst/tasks/{ticket_id}/assignment-recommendations"

        preview = await client.post(root + "/preview", headers=csrf, json=_payload())
        accept = await client.post(
            root + "/accept",
            headers=csrf,
            json={
                "recommendationId": str(uuid4()),
                "previewHash": HASH,
                "selectedUnitId": str(store.unit_id),
                "selectedAnalystUserId": str(store.analyst_id),
                "workPackages": ["Assess reporting"],
            },
        )

    # Deny-as-absence: an analyst is not told that a manager workflow exists.
    assert preview.status_code == 404
    assert accept.status_code == 404
