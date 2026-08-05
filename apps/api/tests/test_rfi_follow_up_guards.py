"""Ownership, state and content guards on requester search follow-up."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from coeus.core.errors import AppError
from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord, TicketTimelineEntry
from coeus.services.rfi_follow_up import RfiFollowUpService

REQUESTER = uuid4()
ACTOR = SimpleNamespace(user_id=REQUESTER, permissions=set())


def _entry(event_type: str, ticket_id: object) -> TicketTimelineEntry:
    return TicketTimelineEntry(
        uuid4(),
        ticket_id,  # type: ignore[arg-type]
        event_type,
        "Synthetic entry.",
        REQUESTER,
        datetime(2026, 8, 4, tzinfo=UTC),
    )


def _ticket(
    *event_types: str,
    state: TicketState = TicketState.NEW_TASKING_CONSENT,
    requester: object = REQUESTER,
) -> TicketRecord:
    ticket_id = uuid4()
    return TicketRecord(
        ticket_id,
        "TCK-0001",
        requester,  # type: ignore[arg-type]
        state,
        IntakeDetails(title="Synthetic"),
        timeline=tuple(_entry(value, ticket_id) for value in event_types),
    )


def _service(ticket: TicketRecord) -> RfiFollowUpService:
    return RfiFollowUpService(
        SimpleNamespace(get_visible_ticket=lambda *_args: ticket),  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
    )


def test_only_the_requester_may_follow_up_on_their_own_search() -> None:
    ticket = _ticket("rfi_search_feedback_requested", requester=uuid4())
    service = _service(ticket)

    with pytest.raises(AppError) as error:
        service.record_feedback(ACTOR, ticket.ticket_id, "The offers missed the port data.")  # type: ignore[arg-type]

    assert error.value.code == "ticket_not_found"
    assert error.value.status_code == 404


@pytest.mark.parametrize(
    "state",
    [TicketState.RFI_SEARCHING, TicketState.ANALYST_ASSIGNMENT],
)
def test_follow_up_only_applies_while_a_decision_is_awaited(state: TicketState) -> None:
    ticket = _ticket("rfi_search_feedback_requested", state=state)
    service = _service(ticket)

    with pytest.raises(AppError) as error:
        service.record_feedback(ACTOR, ticket.ticket_id, "The offers missed the port data.")  # type: ignore[arg-type]

    assert error.value.code == "invalid_ticket_state"


def test_feedback_is_refused_when_none_was_asked_for() -> None:
    ticket = _ticket()
    service = _service(ticket)

    with pytest.raises(AppError) as error:
        service.record_feedback(ACTOR, ticket.ticket_id, "The offers missed the port data.")  # type: ignore[arg-type]

    assert error.value.code == "rfi_search_feedback_unavailable"


@pytest.mark.parametrize("feedback", ["", "  ", "no"])
def test_a_feedback_response_needs_some_content(feedback: str) -> None:
    ticket = _ticket("rfi_search_feedback_requested")
    service = _service(ticket)

    with pytest.raises(AppError) as error:
        service.record_feedback(ACTOR, ticket.ticket_id, feedback)  # type: ignore[arg-type]

    assert error.value.code == "invalid_search_feedback"
    assert error.value.status_code == 422


def test_a_refined_search_needs_recorded_feedback_first() -> None:
    ticket = _ticket("rfi_search_feedback_requested")
    service = _service(ticket)

    with pytest.raises(AppError) as error:
        service.prepare_refined_search(ACTOR, ticket.ticket_id)  # type: ignore[arg-type]

    assert error.value.code == "rfi_search_feedback_required"


def test_a_search_that_is_not_running_cannot_be_marked_incomplete() -> None:
    ticket = _ticket(state=TicketState.NEW_TASKING_CONSENT)
    service = _service(ticket)

    assert (
        service.record_refined_search_incomplete(ACTOR, ticket.ticket_id, "timeout")  # type: ignore[arg-type]
        is ticket
    )
