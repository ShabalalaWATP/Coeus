from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, Thread
from typing import cast
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.auth import AuthenticatedSession, SessionRecord
from coeus.domain.enums import TicketState
from coeus.domain.tickets import TicketRecord
from coeus.main import create_app
from coeus.services.qc_ingestion import QcApprovalInput
from test_qc_api import _acg_id, _approval_payload, _submitted_qc_ticket


def _approval_input(acg_id: str) -> QcApprovalInput:
    payload = _approval_payload(acg_id)
    return QcApprovalInput(
        checklist=cast(dict[str, bool], payload["checklist"]),
        classification_level=cast(int, payload["classificationLevel"]),
        releasability=tuple(cast(list[str], payload["releasability"])),
        handling_caveats=tuple(cast(list[str], payload["handlingCaveats"])),
        acg_ids=frozenset({UUID(acg_id)}),
        reason=cast(str, payload["reason"]),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("winner_state", [TicketState.CANCELLED, TicketState.DISSEMINATION_READY])
async def test_qc_approval_and_cancellation_cannot_both_win(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, winner_state: TicketState
) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Concurrent QC product")
    ticket_uuid = UUID(ticket_id)
    users = app.state.access_services.repository
    requester = users.get_user_by_username("user@example.test")
    qc_manager = users.get_user_by_username("qc.manager@example.test")
    assert requester is not None and qc_manager is not None
    qc_session = SessionRecord(
        "qc-cancel-race-session",
        qc_manager.user_id,
        "qc-cancel-race-csrf",
        datetime.now(UTC) + timedelta(hours=1),
        datetime.now(UTC),
        qc_manager.credential_version,
    )
    app.state.auth_service._sessions.save(qc_session)
    authenticated = AuthenticatedSession(qc_session, qc_manager)
    app.state.quality_control_service.claim(qc_manager, ticket_uuid)
    repository = app.state.ticket_services.tickets._repository
    loser_ready = Event()
    winner_committed = Event()
    if winner_state == TicketState.CANCELLED:
        indexing = app.state.quality_control_service._indexing
        original_index = indexing.index_product

        def paused_index(*args: object, **kwargs: object):
            loser_ready.set()
            assert winner_committed.wait(timeout=5)
            return original_index(*args, **kwargs)

        monkeypatch.setattr(indexing, "index_product", paused_index)
    else:
        lifecycle = app.state.ticket_lifecycle_service
        original_lifecycle_save = lifecycle._save_and_audit

        def paused_lifecycle_save(*args: object, **kwargs: object):
            loser_ready.set()
            assert winner_committed.wait(timeout=5)
            return original_lifecycle_save(*args, **kwargs)

        monkeypatch.setattr(lifecycle, "_save_and_audit", paused_lifecycle_save)
    outcomes: list[TicketRecord | AppError] = []

    def approve() -> None:
        try:
            if winner_state == TicketState.DISSEMINATION_READY:
                assert loser_ready.wait(timeout=5)
            outcomes.append(
                app.state.quality_control_service.approve(
                    authenticated,
                    ticket_uuid,
                    _approval_input(_acg_id(app, "ACG-EU-CYBER")),
                )
            )
            if winner_state == TicketState.DISSEMINATION_READY:
                winner_committed.set()
        except AppError as error:
            outcomes.append(error)

    def cancel() -> None:
        try:
            if winner_state == TicketState.CANCELLED:
                assert loser_ready.wait(timeout=5)
            outcomes.append(
                app.state.ticket_lifecycle_service.cancel(
                    requester, ticket_uuid, "No longer needed"
                )
            )
            if winner_state == TicketState.CANCELLED:
                winner_committed.set()
        except AppError as error:
            outcomes.append(error)

    threads = [Thread(target=approve), Thread(target=cancel)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert all(not thread.is_alive() for thread in threads)
    assert len([result for result in outcomes if isinstance(result, TicketRecord)]) == 1
    errors = [result for result in outcomes if isinstance(result, AppError)]
    assert len(errors) == 1 and errors[0].code == "ticket_changed"
    current = repository.get(ticket_uuid)
    assert current is not None
    assert current.state == winner_state
    products = tuple(
        product
        for product in app.state.store_services.repository.list_products()
        if product.metadata.title == "Concurrent QC product"
    )
    assert len(products) == int(winner_state == TicketState.DISSEMINATION_READY)
