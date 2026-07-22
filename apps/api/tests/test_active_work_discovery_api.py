from dataclasses import replace
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from active_work_test_helpers import prepare_active_work_review
from coeus.core.config import Settings
from coeus.domain.enums import TicketState
from coeus.main import create_app
from coeus.services.active_work_discovery import ActiveWorkDiscoveryService
from test_similar_requests_api import login, similar_ticket_pair


@pytest.mark.asyncio
async def test_customer_can_decline_active_work_before_new_tasking_consent() -> None:
    app = create_app(_settings())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        source_id, _target_id = await similar_ticket_pair(client, str(user["csrfToken"]))
        prepare_active_work_review(app, "user@example.test", source_id)
        continued = await client.post(
            f"/api/v1/similar-requests/tickets/{source_id}/continue",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )

    assert continued.status_code == 200
    assert continued.json()["state"] == "NEW_TASKING_CONSENT"
    source = app.state.ticket_services.tickets._repository.get(UUID(source_id))
    assert source is not None
    assert {offer.status for offer in source.active_work_offers} == {"rejected"}


@pytest.mark.asyncio
async def test_incomplete_active_work_search_must_be_retried_before_consent() -> None:
    app = create_app(_settings())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        source_id, _target_id = await similar_ticket_pair(client, str(user["csrfToken"]))
        actor = app.state.access_services.repository.get_user_by_username("user@example.test")
        assert actor is not None
        service = ActiveWorkDiscoveryService(
            app.state.ticket_services, app.state.similar_request_service
        )
        ticket = app.state.ticket_services.tickets.get_visible_ticket(actor, UUID(source_id))
        app.state.ticket_services.tickets.save_system_update(
            replace(ticket, state=TicketState.NEW_TASKING_CONSENT)
        )
        session_id = client.cookies.get("coeus_session")
        authenticated = app.state.auth_service.require_session(session_id)
        incomplete = service.record_incomplete(
            authenticated, UUID(source_id), "provider_unavailable"
        )
        retried = await client.post(
            f"/api/v1/similar-requests/tickets/{source_id}/retry",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )

    assert incomplete.state == TicketState.ACTIVE_WORK_SEARCH_INCOMPLETE
    assert retried.status_code == 200
    assert retried.json()["state"] in {"ACTIVE_WORK_REVIEW", "NEW_TASKING_CONSENT"}


@pytest.mark.asyncio
async def test_customer_join_is_durable_idempotent_and_closes_source() -> None:
    app = create_app(_settings())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        source_id, target_id = await similar_ticket_pair(client, str(user["csrfToken"]))
        prepare_active_work_review(app, "user@example.test", source_id)
        joined = await client.post(
            f"/api/v1/similar-requests/tickets/{source_id}/join/{target_id}",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )
        repeated = await client.post(
            f"/api/v1/similar-requests/tickets/{source_id}/join/{target_id}",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )

    assert joined.status_code == 200
    assert repeated.status_code == 200
    source = app.state.ticket_services.tickets._repository.get(UUID(source_id))
    target = app.state.ticket_services.tickets._repository.get(UUID(target_id))
    assert source is not None and target is not None
    assert source.state == TicketState.CLOSED_JOINED_EXISTING_WORK
    assert source.duplicate_of_ticket_id == target.ticket_id
    assert source.ticket_id in target.related_ticket_ids
    assert target.collaborators == ()


def _settings() -> Settings:
    return Settings(
        environment="test",
        argon2_memory_cost=8_192,
        persistence_provider="memory",
    )
