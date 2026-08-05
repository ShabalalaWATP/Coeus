"""Unit evidence for canonical assignment ownership writes."""

from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import Connection

from coeus.domain.team_task_ownership import AssignmentOwnershipIntent, WorkflowLeg
from coeus.persistence.team_task_assignment_write import write_assignment_ownership

NOW = datetime(2026, 8, 3, 12, tzinfo=UTC)


class _Result:
    def __init__(self, value: object = None, row: dict[str, object] | None = None) -> None:
        self.value = value
        self.row = row

    def scalar_one(self) -> object:
        return self.value

    def mappings(self) -> "_Result":
        return self

    def first(self) -> dict[str, object] | None:
        return self.row

    def one(self) -> dict[str, object]:
        assert self.row is not None
        return self.row


class _Connection:
    def __init__(self, *results: _Result) -> None:
        self.results = list(results)
        self.calls: list[object] = []

    def execute(self, statement: object, _params: object = None) -> _Result:
        self.calls.append(statement)
        return self.results.pop(0)


def test_write_uses_current_authority_and_returns_new_version() -> None:
    revision_id = uuid4()
    connection = _Connection(
        _Result(NOW),
        _Result(row={"revision_id": revision_id, "policy_version": 4}),
        _Result(row={"version": 2}),
    )
    intent = AssignmentOwnershipIntent(uuid4(), WorkflowLeg.CM_COLLECTION, uuid4(), uuid4())

    assert write_assignment_ownership(cast(Connection, connection), str(uuid4()), intent) == 2
    assert len(connection.calls) == 3


def test_write_rejects_missing_current_delivery_authority() -> None:
    connection = _Connection(_Result(NOW), _Result(row=None))
    intent = AssignmentOwnershipIntent(uuid4(), WorkflowLeg.RFA, uuid4(), uuid4())

    with pytest.raises(ValueError, match="delivery authority"):
        write_assignment_ownership(cast(Connection, connection), str(uuid4()), intent)
