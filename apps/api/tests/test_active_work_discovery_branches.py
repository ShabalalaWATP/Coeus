from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from coeus.core.errors import AppError
from coeus.domain.auth import AuthenticatedSession, RoleName, SessionRecord, UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.services.active_work_discovery import ActiveWorkDiscoveryService


def test_discovery_and_incomplete_retries_are_idempotent() -> None:
    actor = _actor()
    service, tickets = _service()
    review = _ticket(actor, TicketState.ACTIVE_WORK_REVIEW)
    draft = _ticket(actor, TicketState.DRAFT_INTAKE)
    completed = replace(
        _ticket(actor, TicketState.NEW_TASKING_CONSENT),
        timeline=(SimpleNamespace(event_type="active_work_search_completed"),),
    )
    incomplete = _ticket(actor, TicketState.ACTIVE_WORK_SEARCH_INCOMPLETE)
    tickets.tickets.get_visible_ticket.side_effect = (
        review,
        draft,
        completed,
        incomplete,
        draft,
    )

    assert service.discover_automated(actor, review.ticket_id) is review
    assert service.discover_automated(actor, draft.ticket_id) is draft
    assert service.discover_automated(actor, completed.ticket_id) is completed
    authenticated = _authenticated(actor)
    assert service.record_incomplete(authenticated, incomplete.ticket_id, "retry") is incomplete
    assert service.record_incomplete(authenticated, draft.ticket_id, "retry") is draft


def test_visible_offers_drop_decided_hidden_and_closed_targets() -> None:
    actor = _actor()
    service, tickets = _service()
    offer_ids = (uuid4(), uuid4(), uuid4())
    source = replace(
        _ticket(actor, TicketState.ACTIVE_WORK_REVIEW),
        active_work_offers=(
            SimpleNamespace(ticket_id=offer_ids[0], status="rejected"),
            SimpleNamespace(ticket_id=offer_ids[1], status="offered"),
            SimpleNamespace(ticket_id=offer_ids[2], status="offered"),
        ),
    )
    tickets.tickets.get_visible_ticket.side_effect = (
        source,
        AppError(404, "ticket_not_found", "Not found"),
        _ticket(actor, TicketState.CANCELLED, offer_ids[2]),
    )

    assert service.offers(actor, source.ticket_id) == ()


def test_join_and_continue_reject_stale_or_unauthorised_decisions() -> None:
    actor = _actor()
    outsider = replace(actor, user_id=uuid4())
    service, tickets = _service()
    related_id = uuid4()
    offered = SimpleNamespace(ticket_id=related_id, status="offered")
    review = replace(_ticket(actor, TicketState.ACTIVE_WORK_REVIEW), active_work_offers=(offered,))
    no_offer = replace(review, active_work_offers=())
    closed_target = _ticket(actor, TicketState.CANCELLED, related_id)
    tickets.tickets.get_visible_ticket.side_effect = (
        no_offer,
        review,
        closed_target,
        review,
        review,
    )

    with pytest.raises(AppError, match="Similar request was not found"):
        service.join(actor, no_offer.ticket_id, related_id)
    with pytest.raises(AppError, match="no longer open"):
        service.join(actor, review.ticket_id, related_id)
    with pytest.raises(AppError, match="Ticket was not found"):
        service.continue_new_tasking(outsider, review.ticket_id)
    with pytest.raises(AppError, match="No active-work decision is pending"):
        tickets.tickets.get_visible_ticket.side_effect = None
        tickets.tickets.get_visible_ticket.return_value = replace(
            review, state=TicketState.NEW_TASKING_CONSENT
        )
        service.continue_new_tasking(actor, review.ticket_id)


def _service():
    tickets = SimpleNamespace(tickets=MagicMock(), mutations=MagicMock())
    return ActiveWorkDiscoveryService(tickets, MagicMock()), tickets


def _actor() -> UserAccount:
    return UserAccount(
        uuid4(),
        "customer@example.test",
        "Synthetic Customer",
        frozenset({RoleName.USER}),
        frozenset(),
        "unused",
        True,
        2,
    )


def _ticket(actor: UserAccount, state: TicketState, ticket_id=None) -> TicketRecord:
    return TicketRecord(
        ticket_id or uuid4(),
        "RFI-ACTIVE-WORK-BRANCH",
        actor.user_id,
        state,
        IntakeDetails(title="Synthetic active work", operational_question="What changed?"),
    )


def _authenticated(actor: UserAccount) -> AuthenticatedSession:
    return AuthenticatedSession(
        SessionRecord(
            session_id="active-work-session",
            user_id=actor.user_id,
            csrf_token="csrf",  # noqa: S106
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            created_at=datetime.now(UTC),
        ),
        actor,
    )
