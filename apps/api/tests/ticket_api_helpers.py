from typing import Any, cast
from uuid import UUID

from fastapi import FastAPI
from httpx import AsyncClient

from coeus.domain.tickets import TicketRecord
from coeus.services.audit import AuditEvent

SEED_CREDENTIAL = "CoeusLocal1!"


async def login(client: AsyncClient, username: str = "user@example.test") -> dict[str, Any]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": SEED_CREDENTIAL},
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def fail_audit(
    event_type: str,
    actor_user_id: str | None = None,
    metadata: dict[str, str] | None = None,
) -> AuditEvent:
    raise RuntimeError("audit unavailable")


def stored_ticket(app: FastAPI, ticket_id: str) -> TicketRecord:
    ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert ticket is not None
    return cast(TicketRecord, ticket)
