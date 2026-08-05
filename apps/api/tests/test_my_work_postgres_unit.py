"""Unit coverage for personal-work state and row integrity oracles."""

from datetime import UTC, date, datetime
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import RowMapping

from coeus.domain.enums import TicketState
from coeus.domain.my_work import MyWorkColumn, MyWorkIntegrityError, decode_cursor
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.persistence.codec import encode_value
from coeus.persistence.my_work_postgres import _card, _column, _next_cursor

NOW = datetime(2026, 8, 3, 12, tzinfo=UTC)


def _row(
    ticket_state: TicketState = TicketState.ANALYST_IN_PROGRESS,
    package_state: str = "in_progress",
) -> dict[str, object]:
    actor_id, ticket_id = uuid4(), uuid4()
    ticket = TicketRecord(
        ticket_id,
        "TCK-WORK-001",
        uuid4(),
        ticket_state,
        IntakeDetails(title="Synthetic request"),
    )
    return {
        "ticket_id": ticket_id,
        "package_id": uuid4(),
        "payload": encode_value(ticket),
        "workflow_leg": "rfa",
        "my_column": _column(ticket_state, package_state).value,
        "package_state": package_state,
        "accountable_user_id": actor_id,
        "participant_user_id": actor_id,
        "participant_role": "accountable",
        "package_title": "Assess evidence",
        "priority": 2,
        "target_date": date(2026, 8, 8),
        "due_at": NOW,
        "blocked_code": None,
        "review_at": None,
        "ticket_version": 2,
        "ownership_version": 3,
        "package_version": 4,
        "sort_at": NOW,
        "sort_order": 1,
    }


def test_state_oracle_covers_delivery_precedence() -> None:
    assert _column(TicketState.MANAGER_APPROVAL, "blocked") is MyWorkColumn.REVIEW
    assert _column(TicketState.QC_REVIEW, "in_progress") is MyWorkColumn.REVIEW
    assert _column(TicketState.REWORK_REQUIRED, "blocked") is MyWorkColumn.REWORK
    assert _column(TicketState.JIOC_INTERVENTION_HOLD, "blocked") is MyWorkColumn.ON_HOLD
    assert _column(TicketState.ANALYST_IN_PROGRESS, "blocked") is MyWorkColumn.BLOCKED
    assert _column(TicketState.CLOSED_DELIVERED, "in_progress") is MyWorkColumn.COMPLETED
    assert _column(TicketState.CANCELLED, "in_progress") is MyWorkColumn.COMPLETED
    assert _column(TicketState.ANALYST_ASSIGNMENT, "pending") is MyWorkColumn.READY
    assert _column(TicketState.ANALYST_IN_PROGRESS, "ready") is MyWorkColumn.READY
    with pytest.raises(MyWorkIntegrityError, match="unsupported"):
        _column(TicketState.ANALYST_IN_PROGRESS, "unknown")


def test_card_validates_identity_roles_and_cursor_order() -> None:
    row = _row()
    assert _card(cast(RowMapping, row)).package_title == "Assess evidence"
    cursor = decode_cursor(_next_cursor(cast(RowMapping, row)))
    assert cursor is not None and cursor.sort_order == 1

    mismatch = dict(row, ticket_id=uuid4())
    with pytest.raises(MyWorkIntegrityError, match="identity"):
        _card(cast(RowMapping, mismatch))
    bad_role = dict(row, participant_role="contributor")
    with pytest.raises(MyWorkIntegrityError, match="malformed"):
        _card(cast(RowMapping, bad_role))
    wrong_accountable = dict(row, accountable_user_id=uuid4())
    with pytest.raises(MyWorkIntegrityError, match="malformed"):
        _card(cast(RowMapping, wrong_accountable))
    contributor_is_accountable = dict(row, participant_role="contributor")
    with pytest.raises(MyWorkIntegrityError, match="malformed"):
        _card(cast(RowMapping, contributor_is_accountable))
    bad_order = dict(row, sort_at="not-a-date")
    with pytest.raises(MyWorkIntegrityError, match="ordering"):
        _next_cursor(cast(RowMapping, bad_order))
