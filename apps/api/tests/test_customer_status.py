from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.services.customer_status import customer_status


def test_joined_work_exposes_canonical_target_and_skips_unrun_stages() -> None:
    actor = _actor()
    canonical_id = uuid4()
    ticket = _ticket(actor, TicketState.CLOSED_JOINED_EXISTING_WORK, canonical_id)

    status = customer_status(ticket, actor)

    assert status.code == "joined_existing"
    assert status.canonical_ticket_id == canonical_id
    assert status.estimate is None
    assert [item.status for item in status.journey[:2]] == ["complete", "complete"]
    assert all(item.status == "not_required" for item in status.journey[2:])


def test_forecast_pauses_for_customer_action_and_marks_deadline_risk() -> None:
    actor = _actor()
    paused = customer_status(_ticket(actor, TicketState.NEW_TASKING_CONSENT), actor)
    overdue = _ticket(actor, TicketState.ANALYST_IN_PROGRESS)
    overdue = replace(
        overdue,
        intake=IntakeDetails(
            operational_question="What changed?",
            priority="routine",
            deadline="2025-01-01T00:00:00+00:00",
        ),
    )
    active = customer_status(overdue, actor, now=datetime(2026, 7, 18, tzinfo=UTC))

    assert paused.action_required is True
    assert paused.estimate is not None and paused.estimate.status == "paused"
    assert active.estimate is not None and active.estimate.status == "at_risk"
    assert active.estimate.confidence == "low"


@pytest.mark.parametrize(
    ("state", "code"),
    [
        (TicketState.ACTIVE_WORK_REVIEW, "active_work_offered"),
        (TicketState.JIOC_INTERVENTION_HOLD, "jioc_hold"),
        (TicketState.MANAGER_APPROVAL, "manager_review"),
    ],
)
def test_customer_status_projects_new_operational_states(state: TicketState, code: str) -> None:
    actor = _actor()

    status = customer_status(_ticket(actor, state), actor)

    assert status.code == code


def test_rfi_no_match_is_actionable_and_never_presented_as_complete() -> None:
    actor = _actor()

    status = customer_status(_ticket(actor, TicketState.RFI_NO_MATCH), actor)

    assert status.code == "no_match"
    assert status.current_leg == "search"
    assert status.action_required is True
    assert status.action_type == "decide_new_tasking"
    assert status.estimate is not None and status.estimate.status == "paused"


def test_only_terminal_states_use_the_complete_leg() -> None:
    actor = _actor()
    terminal_states = {
        TicketState.CLOSED_DELIVERED,
        TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED,
        TicketState.CLOSED_UNANSWERED,
        TicketState.CLOSED_JOINED_EXISTING_WORK,
        TicketState.CANCELLED,
        TicketState.CLOSED_REQUIREMENT_MET,
        TicketState.CLOSED_REANALYSIS_DECLINED,
    }

    for state in TicketState:
        status = customer_status(_ticket(actor, state), actor)
        assert (status.current_leg == "complete") is (state in terminal_states)


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


def _ticket(actor: UserAccount, state: TicketState, duplicate_id=None) -> TicketRecord:
    return TicketRecord(
        ticket_id=uuid4(),
        reference="RFI-CUSTOMER-STATUS",
        requester_user_id=actor.user_id,
        state=state,
        intake=IntakeDetails(operational_question="What changed?", priority="routine"),
        duplicate_of_ticket_id=duplicate_id,
    )
