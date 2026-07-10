from typing import cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.tickets import TicketRecord
from coeus.main import create_app
from test_similar_requests_api import login, similar_ticket_pair, submitted_ticket


@pytest.mark.asyncio
async def test_customer_join_audit_failure_rolls_back_collaborator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(
        Settings(environment="test", argon2_memory_cost=8_192, persistence_provider="memory")
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        colleague = await login(client, "colleague@example.test")
        target_id = await submitted_ticket(
            client,
            str(colleague["csrfToken"]),
            title="Vessel movements Gulf of Finland",
            question="What vessel movements are occurring around the Gulf of Finland?",
            region="Gulf of Finland",
            description="Track vessel movements near the Gulf of Finland.",
            output_format="movement report",
        )
        admin = await login(client, "admin@example.test")
        source_id = await submitted_ticket(
            client,
            str(admin["csrfToken"]),
            title="Boat traffic near St Petersburg",
            question="What boat traffic is near St Petersburg?",
            region="St Petersburg",
            description="Assess boat traffic near St Petersburg.",
            output_format="traffic picture",
        )
        original = _stored_ticket(app, target_id)
        monkeypatch.setattr(app.state.similar_request_service._audit_log, "record", _fail_audit)

        with pytest.raises(RuntimeError, match="audit unavailable"):
            await client.post(
                f"/api/v1/similar-requests/tickets/{source_id}/join/{target_id}",
                headers={"X-CSRF-Token": str(admin["csrfToken"])},
            )

    target = _stored_ticket(app, target_id)
    assert target.collaborators == original.collaborators
    assert target.timeline == original.timeline


@pytest.mark.asyncio
async def test_manager_link_audit_failure_rolls_back_related_tickets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(
        Settings(environment="test", argon2_memory_cost=8_192, persistence_provider="memory")
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        source_id, target_id = await similar_ticket_pair(client, str(user["csrfToken"]))
        manager = await login(client, "rfa.manager@example.test")
        original_source = _stored_ticket(app, source_id)
        original_target = _stored_ticket(app, target_id)
        monkeypatch.setattr(app.state.similar_request_service._audit_log, "record", _fail_audit)

        with pytest.raises(RuntimeError, match="audit unavailable"):
            await client.post(
                f"/api/v1/similar-requests/routing/{source_id}/link/{target_id}",
                headers={"X-CSRF-Token": str(manager["csrfToken"])},
            )

    source = _stored_ticket(app, source_id)
    target = _stored_ticket(app, target_id)

    assert source.related_ticket_ids == original_source.related_ticket_ids
    assert source.timeline == original_source.timeline
    assert target.related_ticket_ids == original_target.related_ticket_ids
    assert target.timeline == original_target.timeline


def _fail_audit(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("audit unavailable")


def _stored_ticket(app: FastAPI, ticket_id: str) -> TicketRecord:
    ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert ticket is not None
    return cast(TicketRecord, ticket)
