"""Unit coverage for the bounded PostgreSQL board projection."""

from contextlib import AbstractContextManager
from datetime import UTC, datetime
from types import TracebackType
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import Engine, RowMapping

from coeus.domain.enums import TicketState
from coeus.domain.team_task_board import (
    TeamBoardColumn,
    TeamTaskBoardDenied,
    TeamTaskBoardIntegrityError,
)
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.persistence.codec import encode_value
from coeus.persistence.team_task_board_authority import BoardAuthority
from coeus.persistence.team_task_board_postgres import (
    PostgresTeamTaskBoardStore,
    _card,
    _column,
    _optional_datetime,
    _package,
)

NOW = datetime(2026, 8, 3, 12, tzinfo=UTC)


class _Result:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def mappings(self) -> "_Result":
        return self

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.rows)


class _Transaction(AbstractContextManager[None]):
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class _Connection(AbstractContextManager["_Connection"]):
    def __init__(self, *rows: list[dict[str, object]]) -> None:
        self.rows = list(rows)

    def execution_options(self, **_options: object) -> "_Connection":
        return self

    def begin(self) -> _Transaction:
        return _Transaction()

    def execute(self, _statement: object, _params: object = None) -> _Result:
        return _Result(self.rows.pop(0))

    def __enter__(self) -> "_Connection":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class _Engine:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    def connect(self) -> _Connection:
        return self.connection


def _row(state: TicketState = TicketState.ANALYST_IN_PROGRESS) -> dict[str, object]:
    ticket = TicketRecord(
        uuid4(),
        "TCK-UNIT-001",
        uuid4(),
        state,
        IntakeDetails(title="Synthetic task", priority="High"),
    )
    return {
        "ticket_id": ticket.ticket_id,
        "workflow_leg": "rfa",
        "target_date": None,
        "ownership_version": 2,
        "ticket_version": 3,
        "ticket_updated_at": NOW,
        "payload": encode_value(ticket),
        "packages": [],
        "owning_unit_id": uuid4(),
        "unit_name": "Synthetic team",
        "board_column": "in_progress",
    }


def test_store_projects_cards_and_applies_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [_row(), _row()]
    unit_id = rows[0]["owning_unit_id"]
    rows[1]["owning_unit_id"] = unit_id
    connection = _Connection(rows)
    store = PostgresTeamTaskBoardStore(cast(Engine, _Engine(connection)))
    monkeypatch.setattr(
        "coeus.persistence.team_task_board_postgres.transaction_time", lambda _connection: NOW
    )
    monkeypatch.setattr(
        "coeus.persistence.team_task_board_postgres.resolve_board_authority",
        lambda *_args: BoardAuthority((unit_id,), ()),
    )

    board = store.get_board(uuid4(), uuid4(), include_completed=False, limit=1)

    assert board.truncated and board.cards[0].column is TeamBoardColumn.IN_PROGRESS
    with pytest.raises(ValueError, match="between one and 100"):
        store.get_board(uuid4(), uuid4(), include_completed=False, limit=0)


def test_store_denies_when_no_covering_grant(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _Connection()
    store = PostgresTeamTaskBoardStore(cast(Engine, _Engine(connection)))
    monkeypatch.setattr(
        "coeus.persistence.team_task_board_postgres.transaction_time", lambda _connection: NOW
    )
    monkeypatch.setattr(
        "coeus.persistence.team_task_board_postgres.resolve_board_authority",
        lambda *_args: (_ for _ in ()).throw(TeamTaskBoardDenied()),
    )
    with pytest.raises(TeamTaskBoardDenied):
        store.get_board(uuid4(), uuid4(), include_completed=True, limit=50)


def test_card_and_column_oracles_fail_closed() -> None:
    assert _card(cast(RowMapping, _row())).priority == "High"
    invalid = _row()
    invalid["ticket_id"] = uuid4()
    with pytest.raises(TeamTaskBoardIntegrityError, match="identity"):
        _card(cast(RowMapping, invalid))
    supported = {
        TicketState.ANALYST_ASSIGNMENT: TeamBoardColumn.AWAITING_ASSIGNMENT,
        TicketState.MANAGER_APPROVAL: TeamBoardColumn.MANAGER_REVIEW,
        TicketState.QC_REVIEW: TeamBoardColumn.QC_REVIEW,
        TicketState.REWORK_REQUIRED: TeamBoardColumn.REWORK,
        TicketState.JIOC_INTERVENTION_HOLD: TeamBoardColumn.ON_HOLD,
        TicketState.CLOSED_DELIVERED: TeamBoardColumn.COMPLETED_RECENTLY,
        TicketState.CANCELLED: TeamBoardColumn.COMPLETED_RECENTLY,
    }
    assert all(_column(state) is column for state, column in supported.items())
    with pytest.raises(TeamTaskBoardIntegrityError, match="not supported"):
        _column(TicketState.DRAFT_INTAKE)


def test_work_package_projection_accepts_optional_values_and_rejects_malformed_rows() -> None:
    package_id, accountable_id = uuid4(), uuid4()
    complete = {
        "package_id": str(package_id),
        "title": "Review synthetic reporting",
        "state": "in_progress",
        "accountable_user_id": str(accountable_id),
        "estimated_minutes": "90",
        "remaining_minutes": 45,
        "due_at": NOW.isoformat(),
        "priority": "2",
        "version": "3",
    }
    projected = _package(complete)
    assert projected.package_id == package_id
    assert projected.accountable_user_id == accountable_id
    assert projected.due_at == NOW

    empty_optional = {
        **complete,
        "accountable_user_id": None,
        "estimated_minutes": None,
        "remaining_minutes": None,
        "due_at": None,
        "priority": None,
    }
    projected = _package(empty_optional)
    assert projected.accountable_user_id is None
    assert projected.estimated_minutes is None
    assert projected.priority is None
    assert _optional_datetime(NOW) is NOW

    with pytest.raises(TeamTaskBoardIntegrityError, match="malformed"):
        _package("not-a-row")
    with pytest.raises(TeamTaskBoardIntegrityError, match="malformed"):
        _package({**complete, "due_at": object()})
