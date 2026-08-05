"""Bounded grant scans and unit resolution behind workspace authority.

These guards refuse rather than truncate: an actor holding an implausible
number of grants, or a unit whose closure is missing or oversized, must fail
closed instead of silently answering from a partial set.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from coeus.domain.organisation import ManagementAction
from coeus.domain.workspace_operations import WorkspaceOperationsDenied, WorkspaceScope
from coeus.domain.workspace_productivity import WorkspaceRecordDenied
from coeus.persistence.workspace_operations_authority import resolve_workspace_authority
from coeus.persistence.workspace_productivity_authority import require_action

NOW = datetime(2026, 8, 5, 12, tzinfo=UTC)
ACTOR, UNIT = uuid4(), uuid4()


class _Result:
    def __init__(self, rows: tuple[object, ...]) -> None:
        self._rows = rows

    def mappings(self) -> "_Result":
        return self

    def first(self) -> object | None:
        return self._rows[0] if self._rows else None

    def __iter__(self) -> object:
        return iter(self._rows)


class _Connection:
    """Returns each queued result in turn, so query order is the fixture."""

    def __init__(self, *results: tuple[object, ...]) -> None:
        self._results = list(results)

    def execute(self, *_args: object, **_kwargs: object) -> _Result:
        return _Result(self._results.pop(0) if self._results else ())


def _grants(count: int, *, include_descendants: bool = True) -> tuple[object, ...]:
    return tuple(
        {"grant_id": uuid4(), "version": 1, "include_descendants": include_descendants}
        for _ in range(count)
    )


def _active() -> tuple[object, ...]:
    return ({"is_active": True},)


def test_an_implausible_number_of_workspace_grants_is_refused() -> None:
    connection = _Connection(_active(), _grants(201))

    with pytest.raises(WorkspaceOperationsDenied):
        resolve_workspace_authority(
            connection,  # type: ignore[arg-type]
            ACTOR,
            UNIT,
            ManagementAction.TASK_VIEW,
            WorkspaceScope.DIRECT,
            NOW,
        )


def test_a_direct_only_grant_cannot_answer_a_descendant_scope() -> None:
    connection = _Connection(_active(), _grants(1, include_descendants=False))

    with pytest.raises(WorkspaceOperationsDenied):
        resolve_workspace_authority(
            connection,  # type: ignore[arg-type]
            ACTOR,
            UNIT,
            ManagementAction.TASK_VIEW,
            WorkspaceScope.DESCENDANTS,
            NOW,
        )


def test_an_inactive_actor_is_refused_without_leaking_a_neighbouring_error() -> None:
    connection = _Connection(({"is_active": False},))

    with pytest.raises(WorkspaceOperationsDenied):
        resolve_workspace_authority(
            connection,  # type: ignore[arg-type]
            ACTOR,
            UNIT,
            ManagementAction.TASK_VIEW,
            WorkspaceScope.DIRECT,
            NOW,
        )


def test_an_implausible_number_of_record_grants_is_refused() -> None:
    connection = _Connection(_grants(201))

    with pytest.raises(WorkspaceRecordDenied):
        require_action(connection, ACTOR, UNIT, ManagementAction.TASK_VIEW, NOW)  # type: ignore[arg-type]


def test_a_grant_at_another_version_is_passed_over() -> None:
    connection = _Connection(_grants(1))

    with pytest.raises(WorkspaceRecordDenied):
        require_action(
            connection,  # type: ignore[arg-type]
            ACTOR,
            UNIT,
            ManagementAction.TASK_VIEW,
            NOW,
            expected_version=9,
        )


def _unit_ids(scope: WorkspaceScope, closure: tuple[object, ...]) -> tuple[UUID, ...]:
    from coeus.persistence.workspace_operations_authority import _unit_ids as resolve

    return resolve(_Connection(closure), UNIT, scope)  # type: ignore[arg-type]


def test_a_closed_unit_cannot_answer_a_direct_scope() -> None:
    with pytest.raises(WorkspaceOperationsDenied):
        _unit_ids(WorkspaceScope.DIRECT, ())


def test_an_empty_or_oversized_closure_is_refused() -> None:
    with pytest.raises(WorkspaceOperationsDenied):
        _unit_ids(WorkspaceScope.DESCENDANTS, ())
    with pytest.raises(WorkspaceOperationsDenied):
        _unit_ids(WorkspaceScope.DESCENDANTS, tuple([(uuid4(),)] * 1001))
