from dataclasses import replace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.enums import TicketState
from coeus.main import create_app
from coeus.services import similar_request_consolidation
from coeus.services.similar_request_consolidation import mark_duplicate_ticket
from test_similar_requests_api import login, similar_ticket_pair


@pytest.mark.asyncio
async def test_manager_marks_and_withdraws_a_confirmed_duplicate_idempotently() -> None:
    app = create_app(
        Settings(environment="test", argon2_memory_cost=8_192, persistence_provider="memory")
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        source_id, target_id = await similar_ticket_pair(client, str(user["csrfToken"]))
        denied = await client.post(
            f"/api/v1/similar-requests/routing/{source_id}/duplicate/{target_id}",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={"withdrawSource": True},
        )
        manager = await login(client, "rfa.manager@example.test")
        marked = await client.post(
            f"/api/v1/similar-requests/routing/{source_id}/duplicate/{target_id}",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"withdrawSource": True},
        )
        repeated = await client.post(
            f"/api/v1/similar-requests/routing/{source_id}/duplicate/{target_id}",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"withdrawSource": True},
        )

    assert denied.status_code == 403
    assert marked.status_code == 200
    assert marked.json()["matches"][0]["alreadyMarkedDuplicate"] is True
    assert repeated.status_code == 200
    source = app.state.ticket_services.tickets._repository.get(UUID(source_id))
    target = app.state.ticket_services.tickets._repository.get(UUID(target_id))
    assert source is not None and target is not None
    assert source.state.value == "CANCELLED"
    assert source.duplicate_of_ticket_id == target.ticket_id
    assert target.ticket_id in source.related_ticket_ids
    assert source.ticket_id in target.related_ticket_ids
    assert sum(item.event_type == "duplicate_marked" for item in source.timeline) == 1
    audit_types = [event.event_type for event in app.state.auth_service.audit_log.list_events()]
    assert audit_types.count("ticket_duplicate_marked") == 2


@pytest.mark.asyncio
async def test_duplicate_controls_reject_invalid_pairs_states_and_withdrawals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(
        Settings(environment="test", argon2_memory_cost=8_192, persistence_provider="memory")
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user_session = await login(client, "user@example.test")
        source_id, target_id = await similar_ticket_pair(client, str(user_session["csrfToken"]))

    users = app.state.auth_service._users
    user = users.get_by_username("user@example.test")
    manager = users.get_by_username("rfa.manager@example.test")
    assert user is not None and manager is not None
    repository = app.state.ticket_services.tickets._repository
    source = repository.get(UUID(source_id))
    target = repository.get(UUID(target_id))
    assert source is not None and target is not None

    with pytest.raises(AppError, match="cannot duplicate itself"):
        similar_request_consolidation._validate_pair(source, source)
    with pytest.raises(AppError, match="another duplicate target"):
        similar_request_consolidation._validate_pair(
            replace(source, duplicate_of_ticket_id=uuid4()), target
        )
    with pytest.raises(AppError, match="Permission is required"):
        mark_duplicate_ticket(
            app.state.ticket_services,
            app.state.auth_service.audit_log,
            app.state.embedding_service,
            user,
            source.ticket_id,
            target.ticket_id,
            withdraw_source=False,
        )

    monkeypatch.setattr(
        similar_request_consolidation,
        "score_similar_requests",
        lambda *_args, **_kwargs: (),
    )
    with pytest.raises(AppError, match="selected ticket is not a match"):
        mark_duplicate_ticket(
            app.state.ticket_services,
            app.state.auth_service.audit_log,
            app.state.embedding_service,
            manager,
            source.ticket_id,
            target.ticket_id,
            withdraw_source=False,
        )

    repository.save(replace(source, state=TicketState.CANCELLED))
    with pytest.raises(AppError, match="Only active tickets"):
        mark_duplicate_ticket(
            app.state.ticket_services,
            app.state.auth_service.audit_log,
            app.state.embedding_service,
            manager,
            source.ticket_id,
            target.ticket_id,
            withdraw_source=False,
            similarity_verified=True,
        )

    blocked = replace(source, disseminations=(cast(Any, object()),))
    repository.save(blocked)
    with pytest.raises(AppError, match="cannot be withdrawn"):
        mark_duplicate_ticket(
            app.state.ticket_services,
            app.state.auth_service.audit_log,
            app.state.embedding_service,
            manager,
            source.ticket_id,
            target.ticket_id,
            withdraw_source=True,
            similarity_verified=True,
        )
