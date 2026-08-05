"""Defensive management-board query, cursor and projection oracles."""

from datetime import UTC, date, datetime, timedelta
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import RowMapping

from coeus.domain.enums import TicketState
from coeus.domain.team_task_board import (
    TeamBoardColumn,
    TeamBoardCursor,
    TeamBoardQuery,
    TeamTaskBoardIntegrityError,
    TeamTaskPackage,
    decode_board_cursor,
    encode_board_cursor,
)
from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.persistence.team_task_board_postgres import (
    _aggregate,
    _column,
    _completed_after,
    _cursor_row,
    _row_cursor,
)

NOW = datetime(2026, 8, 4, 12, tzinfo=UTC)


def test_board_cursor_round_trips_nullable_dates_and_rejects_malformed_values() -> None:
    for target in (None, date(2026, 8, 20)):
        cursor = TeamBoardCursor(uuid4(), target, uuid4(), WorkflowLeg.RFA)
        assert decode_board_cursor(encode_board_cursor(cursor)) == cursor
    for invalid in ("", "%%%", "e30", "WzEsMiwzXQ"):
        with pytest.raises(ValueError, match="cursor is invalid"):
            decode_board_cursor(invalid)


@pytest.mark.parametrize(
    "values",
    (
        {"limit": 0},
        {"limit": 101},
        {"unit_ids": tuple(uuid4() for _ in range(21))},
        {"due_from": date(2026, 8, 3), "due_to": date(2026, 8, 2)},
        {"priority": ""},
        {"priority": "x" * 41},
    ),
)
def test_board_query_rejects_unbounded_or_inconsistent_filters(values: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        TeamBoardQuery(**values)  # type: ignore[arg-type]


def test_work_package_state_oracle_derives_ready_blocked_and_active_columns() -> None:
    pending = _package("pending")
    blocked = _package("blocked")
    active = _package("in_progress")
    assert _column(TicketState.ANALYST_IN_PROGRESS, (pending,)) is TeamBoardColumn.READY
    assert _column(TicketState.ANALYST_IN_PROGRESS, (blocked,)) is TeamBoardColumn.BLOCKED
    assert _column(TicketState.ANALYST_IN_PROGRESS, (active,)) is TeamBoardColumn.IN_PROGRESS
    assert _column(TicketState.ANALYST_IN_PROGRESS) is TeamBoardColumn.IN_PROGRESS


def test_completed_window_and_aggregate_projection_fail_closed() -> None:
    assert _completed_after(None, NOW) == NOW.date() - timedelta(days=30)
    assert _completed_after(NOW.date() - timedelta(days=90), NOW) == NOW.date() - timedelta(days=90)
    for invalid in (NOW.date() - timedelta(days=91), NOW.date() + timedelta(days=1)):
        with pytest.raises(ValueError, match="previous 90 days"):
            _completed_after(invalid, NOW)
    aggregate = _aggregate(
        cast(
            RowMapping,
            {
                "owning_unit_id": uuid4(),
                "unit_name": "Child team",
                "board_column": "blocked",
                "item_count": "5",
            },
        )
    )
    assert aggregate.column is TeamBoardColumn.BLOCKED and aggregate.count == 5
    suppressed = _aggregate(
        cast(
            RowMapping,
            {
                "owning_unit_id": uuid4(),
                "unit_name": "Small child team",
                "board_column": "ready",
                "item_count": 4,
            },
        )
    )
    assert suppressed.suppressed and suppressed.count is None
    for malformed in ({}, {"item_count": -1}):
        with pytest.raises(TeamTaskBoardIntegrityError, match="aggregate"):
            _aggregate(cast(RowMapping, malformed))


def test_cursor_selection_handles_exact_page_candidate_cap_and_empty_rows() -> None:
    row = cast(
        RowMapping,
        {
            "owning_unit_id": uuid4(),
            "target_date": None,
            "ticket_id": uuid4(),
            "workflow_leg": "rfa",
        },
    )
    assert _cursor_row((row,), (), 1, False) is None
    assert _cursor_row((row,), (), 1, True) is row
    assert _cursor_row((), (), 1, True) is None
    assert decode_board_cursor(_row_cursor(row)) == TeamBoardCursor(
        row["owning_unit_id"], None, row["ticket_id"], WorkflowLeg.RFA
    )


def _package(state: str) -> TeamTaskPackage:
    return TeamTaskPackage(uuid4(), "Package", state, None, None, None, None, None, 1)
