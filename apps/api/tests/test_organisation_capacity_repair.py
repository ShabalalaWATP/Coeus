from contextlib import AbstractContextManager
from types import TracebackType
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import Connection, Engine

from coeus.persistence import organisation_capacity_repair as repair


class _Result:
    def __init__(
        self, rows: list[dict[str, object]] | None = None, *, first: object = None
    ) -> None:
        self.rows = rows or []
        self._first = first

    def mappings(self) -> "_Result":
        return self

    def first(self) -> object:
        return self._first

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
        self.disposed = False

    def begin(self) -> _Begin:
        return _Begin(self.connection)

    def dispose(self) -> None:
        self.disposed = True


def test_inspection_is_bounded_and_redacted() -> None:
    rows = [
        {"code": "closure_row_missing", "object_id": uuid4(), "private_note": "hidden"}
        for _ in range(501)
    ]
    connection = _Connection(
        _Result(rows),
        _Result([{"code": "task_ownership_missing", "object_id": uuid4()}]),
        _Result(
            [
                {
                    "code": "expired_hold",
                    "object_id": uuid4(),
                    "repairable": True,
                    "user_id": uuid4(),
                }
            ]
        ),
    )

    report = repair._inspect(cast(Connection, connection))

    assert report.truncated and len(report.topology_issues) == 500
    assert report.ownership_issues[0].repairable is False
    assert report.reservation_issues[0].repairable is True
    assert "hidden" not in str(report.to_dict())
    assert "user_id" not in str(report.to_dict())


def test_repair_refuses_blockers_and_updates_only_derived_states() -> None:
    blocker = repair.RepairIssue("reservation_package_mismatch", str(uuid4()), False)
    with pytest.raises(RuntimeError, match="manual disposition"):
        repair._repair_reservations(cast(Connection, _Connection()), (blocker,))

    expired_id, terminal_id = str(uuid4()), str(uuid4())
    connection = _Connection(_Result(first=(expired_id,)), _Result(first=(terminal_id,)))
    changed = repair._repair_reservations(
        cast(Connection, connection),
        (
            repair.RepairIssue("expired_hold", expired_id, True),
            repair.RepairIssue("terminal_package_reservation", terminal_id, True),
        ),
    )

    assert changed == (expired_id, terminal_id)
    assert connection.calls[0][1]["target_state"] == "expired"  # type: ignore[index]
    assert connection.calls[1][1]["target_state"] == "released"  # type: ignore[index]

    unsupported = repair.RepairIssue("unknown", str(uuid4()), True)
    with pytest.raises(RuntimeError, match="Unsupported"):
        repair._repair_reservations(cast(Connection, _Connection()), (unsupported,))

    unchanged = repair._repair_reservations(
        cast(Connection, _Connection(_Result(first=None))),
        (repair.RepairIssue("expired_hold", str(uuid4()), True),),
    )
    assert unchanged == ()


def test_entrypoint_requires_review_and_records_atomic_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operator = uuid4()
    with pytest.raises(ValueError, match="reviewed confirmation"):
        repair.inspect_or_repair_organisation_capacity(
            "postgresql://unused", action="repair-reservations", operator_user_id=operator
        )
    with pytest.raises(ValueError, match="500"):
        repair.inspect_or_repair_organisation_capacity(
            "postgresql://unused",
            action="repair-reservations",
            operator_user_id=operator,
            reason="x" * 501,
            reviewed=True,
        )

    connection, engine = _Connection(_Result(), _Result()), _Engine(_Connection())
    engine.connection = connection
    before = repair.OrganisationCapacityRepairReport(
        (), (), (repair.RepairIssue("expired_hold", str(uuid4()), True),)
    )
    after = repair.OrganisationCapacityRepairReport((), (), ())
    inspections = iter((before, after))
    monkeypatch.setattr(repair, "create_engine", lambda *_args, **_kwargs: cast(Engine, engine))
    monkeypatch.setattr(repair, "_inspect", lambda _connection: next(inspections))
    monkeypatch.setattr(repair, "_repair_reservations", lambda *_args: (str(uuid4()),))

    report = repair.inspect_or_repair_organisation_capacity(
        "postgresql://unused",
        action="repair-reservations",
        operator_user_id=operator,
        reason="Reviewed terminal package evidence",
        reviewed=True,
    )

    assert report.changed_count == 1 and not report.has_issues
    assert len(connection.calls) == 4  # isolation, advisory lock, audit and outbox
    assert engine.disposed

    with pytest.raises(ValueError, match="Operator identity"):
        repair._append_evidence(cast(Connection, _Connection()), None, "reviewed", (str(uuid4()),))


def test_empty_repair_is_idempotent_and_inspection_disposes_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection, engine = _Connection(_Result(), _Result()), _Engine(_Connection())
    engine.connection = connection
    empty = repair.OrganisationCapacityRepairReport((), (), ())
    monkeypatch.setattr(repair, "create_engine", lambda *_args, **_kwargs: cast(Engine, engine))
    monkeypatch.setattr(repair, "_inspect", lambda _connection: empty)

    report = repair.inspect_or_repair_organisation_capacity("postgresql://unused")

    assert report == empty and engine.disposed
    assert len(connection.calls) == 2


def test_repair_refuses_a_truncated_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    connection, engine = _Connection(_Result(), _Result()), _Engine(_Connection())
    engine.connection = connection
    truncated = repair.OrganisationCapacityRepairReport((), (), (), truncated=True)
    monkeypatch.setattr(repair, "create_engine", lambda *_args, **_kwargs: cast(Engine, engine))
    monkeypatch.setattr(repair, "_inspect", lambda _connection: truncated)

    with pytest.raises(RuntimeError, match="truncated"):
        repair.inspect_or_repair_organisation_capacity(
            "postgresql://unused",
            action="repair-reservations",
            operator_user_id=uuid4(),
            reason="Reviewed bounded evidence",
            reviewed=True,
        )
    assert engine.disposed
