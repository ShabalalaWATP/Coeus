"""Search feedback and refinement state derived from a ticket timeline."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from coeus.core.errors import AppError
from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord, TicketTimelineEntry
from coeus.services.rfi_follow_up import RfiFollowUpService

TICKET, ACTOR = uuid4(), uuid4()


def _entry(event_type: str) -> TicketTimelineEntry:
    return TicketTimelineEntry(
        uuid4(), TICKET, event_type, "Synthetic entry.", ACTOR, datetime(2026, 8, 4, tzinfo=UTC)
    )


def _ticket(*event_types: str) -> TicketRecord:
    return TicketRecord(
        TICKET,
        "TCK-0001",
        ACTOR,
        TicketState.NEW_TASKING_CONSENT,
        IntakeDetails(title="Synthetic"),
        timeline=tuple(_entry(value) for value in event_types),
    )


def test_a_ticket_with_no_history_is_awaiting_nothing() -> None:
    ticket = _ticket()

    assert not RfiFollowUpService.feedback_pending(ticket)
    assert not RfiFollowUpService.feedback_recorded_for_latest_request(ticket)
    assert not RfiFollowUpService.refinement_available(ticket)
    RfiFollowUpService.require_standard_retry_available(ticket)


def test_a_requested_feedback_blocks_a_standard_retry_until_it_is_answered() -> None:
    requested = _ticket("rfi_search_feedback_requested")

    assert RfiFollowUpService.feedback_pending(requested)
    with pytest.raises(AppError) as error:
        RfiFollowUpService.require_standard_retry_available(requested)
    assert error.value.code == "rfi_search_feedback_required"


def test_recorded_feedback_opens_the_refinement_route_instead() -> None:
    answered = _ticket("rfi_search_feedback_requested", "rfi_search_feedback_recorded")

    assert not RfiFollowUpService.feedback_pending(answered)
    assert RfiFollowUpService.feedback_recorded_for_latest_request(answered)
    assert RfiFollowUpService.refinement_available(answered)
    with pytest.raises(AppError) as error:
        RfiFollowUpService.require_standard_retry_available(answered)
    assert error.value.code == "rfi_refine_required"


def test_a_started_refinement_consumes_the_recorded_feedback() -> None:
    refined = _ticket(
        "rfi_search_feedback_requested",
        "rfi_search_feedback_recorded",
        "rfi_refined_search_started",
    )

    assert not RfiFollowUpService.refinement_available(refined)
    RfiFollowUpService.require_standard_retry_available(refined)


def test_a_second_request_after_a_refinement_is_pending_again() -> None:
    reopened = _ticket(
        "rfi_search_feedback_requested",
        "rfi_search_feedback_recorded",
        "rfi_refined_search_started",
        "rfi_search_feedback_requested",
    )

    assert RfiFollowUpService.feedback_pending(reopened)
    assert not RfiFollowUpService.feedback_recorded_for_latest_request(reopened)
    assert not RfiFollowUpService.refinement_available(reopened)


def test_feedback_recorded_without_a_request_does_not_open_refinement() -> None:
    orphan = _ticket("rfi_search_feedback_recorded")

    assert not RfiFollowUpService.feedback_pending(orphan)
    assert not RfiFollowUpService.feedback_recorded_for_latest_request(orphan)
    assert not RfiFollowUpService.refinement_available(orphan)


def test_unrelated_timeline_entries_are_ignored() -> None:
    noisy = _ticket(
        "ticket_submitted",
        "rfi_search_feedback_requested",
        "product_offer_rejected",
        "rfi_search_feedback_recorded",
        "comment_added",
    )

    assert RfiFollowUpService.refinement_available(noisy)
