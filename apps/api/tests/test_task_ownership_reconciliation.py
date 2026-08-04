"""Unit coverage for bounded historical task-ownership reconciliation."""

from contextlib import AbstractContextManager
from datetime import UTC, datetime
from types import TracebackType
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.domain.enums import TicketState
from coeus.domain.task_ownership_reconciliation import (
    TaskOwnershipReconciliationLimit,
    TaskOwnershipReconciliationResult,
)
from coeus.domain.tickets import AnalystAssignment, IntakeDetails, RoutingRoute, TicketRecord
from coeus.persistence.codec import encode_value
from coeus.persistence.task_ownership_reconciliation_postgres import (
    PostgresTaskOwnershipReconciliationStore,
    _active_by_route,
    _complete,
    _completed,
    _digest,
    _finding,
    _reconcile_rows,
    _start,
    _stored_result,
    _target_date,
)
from coeus.services.task_ownership_reconciliation import TaskOwnershipReconciliationService

NOW = datetime(2026, 8, 3, 12, tzinfo=UTC)


class _Result:
    def __init__(
        self,
        *,
        value: object = None,
        row: dict[str, object] | None = None,
        rows: list[dict[str, object]] | None = None,
    ) -> None:
        self.value, self.row, self.rows = value, row, rows or []

    def scalar_one(self) -> object:
        return self.value

    def scalar_one_or_none(self) -> object:
        return self.value

    def mappings(self) -> "_Result":
        return self

    def first(self) -> dict[str, object] | None:
        return self.row

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.rows)


class _Connection:
    def __init__(self, *results: _Result) -> None:
        self.results = list(results)
        self.calls: list[tuple[object, object]] = []

    def execute(self, statement: object, params: object = None) -> _Result:
        self.calls.append((statement, params))
        return self.results.pop(0) if self.results else _Result()


class _Begin(AbstractContextManager[_Connection]):
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    def __enter__(self) -> _Connection:
        return self.connection

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

    def begin(self) -> _Begin:
        return _Begin(self.connection)


def _assignment(ticket_id, team_id, route=RoutingRoute.RFA):  # type: ignore[no-untyped-def]
    return AnalystAssignment(uuid4(), ticket_id, uuid4(), uuid4(), route, NOW, team_id, "Synthetic")


def _ticket(*assignments: AnalystAssignment, deadline: str | None = "2026-08-21") -> TicketRecord:
    ticket_id = assignments[0].ticket_id if assignments else uuid4()
    return TicketRecord(
        ticket_id,
        "TCK-UNIT-001",
        uuid4(),
        TicketState.ANALYST_IN_PROGRESS,
        IntakeDetails(title="Synthetic task", deadline=deadline),
        analyst_assignments=assignments,
    )


def _row(ticket: TicketRecord) -> RowMapping:
    return cast(
        RowMapping,
        {
            "ticket_id": ticket.ticket_id,
            "payload": encode_value(ticket),
            "canonical_hash": "a" * 64,
        },
    )


def test_store_applies_once_and_service_forwards(monkeypatch: pytest.MonkeyPatch) -> None:
    ticket = _ticket()
    connection = _Connection(
        _Result(),
        _Result(value=NOW),
        _Result(rows=[dict(_row(ticket))]),
        _Result(row=None),
    )
    store = PostgresTaskOwnershipReconciliationStore(cast(Engine, _Engine(connection)))
    calls: list[str] = []
    monkeypatch.setattr(
        "coeus.persistence.task_ownership_reconciliation_postgres._start",
        lambda *_args: calls.append("start"),
    )
    monkeypatch.setattr(
        "coeus.persistence.task_ownership_reconciliation_postgres._reconcile_rows",
        lambda *_args: (2, 3, 4),
    )
    monkeypatch.setattr(
        "coeus.persistence.task_ownership_reconciliation_postgres._complete",
        lambda *_args: calls.append("complete"),
    )

    result = TaskOwnershipReconciliationService(store).reconcile()

    assert (result.scanned_tickets, result.created_ownerships, result.findings) == (1, 2, 4)
    assert calls == ["start", "complete"]


def test_store_returns_completed_checkpoint_and_rejects_unbounded_corpus() -> None:
    cursor = {
        "scanned_tickets": 7,
        "created_ownerships": 2,
        "existing_ownerships": 4,
        "findings": 1,
    }
    connection = _Connection(
        _Result(), _Result(value=NOW), _Result(rows=[]), _Result(row={"cursor": cursor})
    )
    result = PostgresTaskOwnershipReconciliationStore(cast(Engine, _Engine(connection))).reconcile()
    assert result.already_applied and result.scanned_tickets == 7

    too_many = [{"ticket_id": uuid4(), "canonical_hash": "x", "payload": {}}] * 5_001
    connection = _Connection(_Result(), _Result(value=NOW), _Result(rows=too_many))
    with pytest.raises(TaskOwnershipReconciliationLimit):
        PostgresTaskOwnershipReconciliationStore(cast(Engine, _Engine(connection))).reconcile()


def test_reconcile_rows_creates_existing_and_quarantines(monkeypatch: pytest.MonkeyPatch) -> None:
    first_id, second_id, team_id = uuid4(), uuid4(), uuid4()
    good = _ticket(_assignment(first_id, team_id))
    ambiguous = _ticket(_assignment(second_id, team_id), _assignment(second_id, uuid4()))
    invalid = cast(RowMapping, {"ticket_id": uuid4(), "payload": {}, "canonical_hash": "b"})
    connection = _Connection(_Result(value=None), _Result(value=team_id))
    findings: list[str] = []
    monkeypatch.setattr(
        "coeus.persistence.task_ownership_reconciliation_postgres._finding",
        lambda _connection, _checkpoint, _at, _source, code: findings.append(code),
    )
    writes: list[object] = []
    monkeypatch.setattr(
        "coeus.persistence.task_ownership_reconciliation_postgres.write_assignment_ownership",
        lambda _connection, _ticket_id, intent: writes.append(intent),
    )
    package_writes: list[bool] = []
    monkeypatch.setattr(
        "coeus.persistence.task_ownership_reconciliation_postgres.write_assignment_work_packages",
        lambda _connection, _ticket, _intent, *, only_missing: package_writes.append(only_missing),
    )

    counts = _reconcile_rows(
        cast(Connection, connection), uuid4(), NOW, (_row(good), _row(ambiguous), invalid)
    )

    assert counts == (1, 0, 2)
    assert len(writes) == 1
    assert findings == ["ownership_ambiguous", "invalid_ticket"]

    existing = _reconcile_rows(cast(Connection, connection), uuid4(), NOW, (_row(good),))
    assert existing == (0, 1, 0)
    assert package_writes == [True, True]


def test_missing_authority_and_conflicting_owner_become_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticket_id, team_id = uuid4(), uuid4()
    ticket = _ticket(_assignment(ticket_id, team_id))
    findings: list[str] = []
    monkeypatch.setattr(
        "coeus.persistence.task_ownership_reconciliation_postgres._finding",
        lambda _connection, _checkpoint, _at, _source, code: findings.append(code),
    )
    monkeypatch.setattr(
        "coeus.persistence.task_ownership_reconciliation_postgres.write_assignment_ownership",
        lambda *_args: (_ for _ in ()).throw(ValueError("missing")),
    )
    missing = _reconcile_rows(
        cast(Connection, _Connection(_Result(value=None))), uuid4(), NOW, (_row(ticket),)
    )
    conflict = _reconcile_rows(
        cast(Connection, _Connection(_Result(value=uuid4()))), uuid4(), NOW, (_row(ticket),)
    )
    assert missing == conflict == (0, 0, 1)
    assert findings == ["delivery_authority_missing", "ownership_conflict"]


def test_helpers_cover_routes_dates_digest_and_evidence_writes() -> None:
    ticket_id = uuid4()
    rfa = _assignment(ticket_id, uuid4())
    cm = _assignment(ticket_id, uuid4(), RoutingRoute.CM)
    inactive = AnalystAssignment(**{**vars(rfa), "assignment_id": uuid4(), "active": False})
    grouped = _active_by_route(_ticket(rfa, cm, inactive))
    assert set(grouped) == {RoutingRoute.RFA, RoutingRoute.CM}
    assert _target_date(_ticket(rfa)) is not None
    assert _target_date(_ticket(rfa, deadline="not-a-date")) is None
    assert _target_date(_ticket(rfa, deadline=None)) is None
    assert len(_digest((_row(_ticket(rfa)),))) == 64

    checkpoint_id = uuid4()
    stored = _stored_result(
        cast(
            RowMapping,
            {
                "cursor": {
                    "scanned_tickets": 3,
                    "created_ownerships": 1,
                    "existing_ownerships": 1,
                    "findings": 1,
                }
            },
        ),
        checkpoint_id,
        NOW,
    )
    assert stored.already_applied
    connection = _Connection(_Result(row=None))
    assert _completed(cast(Connection, connection), checkpoint_id) is None
    _start(cast(Connection, connection), checkpoint_id, "c" * 64, NOW)
    _finding(cast(Connection, connection), checkpoint_id, NOW, "ticket:rfa", "ambiguous")
    _complete(
        cast(Connection, connection),
        TaskOwnershipReconciliationResult(checkpoint_id, NOW, 3, 1, 1, 1),
    )
    assert len(connection.calls) == 5
