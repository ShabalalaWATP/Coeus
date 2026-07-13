from dataclasses import replace
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.tickets import TicketRecord
from coeus.main import create_app
from test_qc_api import _submitted_qc_ticket
from test_qc_claim_api import _add_second_qc_reviewer


@pytest.mark.asyncio
async def test_qc_assignment_rejects_missing_authority_and_invalid_states() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    second_username = _add_second_qc_reviewer(app)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "QC state guards")
    users = app.state.access_services.repository
    actor = users.get_user_by_username("qc.manager@example.test")
    second = users.get_user_by_username(second_username)
    assert actor is not None and second is not None
    service = app.state.quality_control_service
    with pytest.raises(AppError, match="Permission denied"):
        service.queue(replace(actor, permissions=frozenset()))
    with pytest.raises(AppError, match="Permission denied"):
        service.queue(replace(actor, roles=frozenset()))
    repository = app.state.ticket_services.tickets._repository
    ticket = repository.get(UUID(ticket_id))
    assert ticket is not None
    released = replace(
        ticket,
        state=type(ticket.state).DISSEMINATION_READY,
        qc_reviewer_user_id=actor.user_id,
    )
    repository.save(released)
    assert service.details(actor, released.ticket_id) == released
    with pytest.raises(AppError) as hidden:
        service.details(second, released.ticket_id)
    assert hidden.value.code == "product_not_found"
    invalid = replace(released, state=type(ticket.state).DRAFT_INTAKE)
    repository.save(invalid)
    with pytest.raises(AppError) as missing:
        service.details(actor, invalid.ticket_id)
    with pytest.raises(AppError) as wrong_state:
        service.claim(actor, invalid.ticket_id)
    assert missing.value.code == "product_not_found"
    assert wrong_state.value.code == "invalid_ticket_state"


@pytest.mark.asyncio
async def test_qc_claim_recovers_an_ambiguous_same_reviewer_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Ambiguous QC claim")
    actor = app.state.access_services.repository.get_user_by_username("qc.manager@example.test")
    assert actor is not None
    repository = app.state.ticket_services.tickets._repository

    def commit_then_conflict(
        _expected: TicketRecord, proposed: TicketRecord, *_args: object
    ) -> None:
        repository.save(proposed)
        raise AppError(409, "ticket_changed", "Ticket changed.")

    monkeypatch.setattr(
        app.state.ticket_services.mutations, "save_audited_if_current", commit_then_conflict
    )
    claimed = app.state.quality_control_service.claim(actor, UUID(ticket_id))
    assert claimed.qc_reviewer_user_id == actor.user_id
