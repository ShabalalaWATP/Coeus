"""Branch guards for merge and split PostgreSQL command stores."""

from dataclasses import replace
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import Connection

from coeus.domain.organisation_merge import (
    OrganisationMergeCommand,
    OrganisationMergeConflict,
    OrganisationMergeImpact,
    OrganisationMergePlan,
)
from coeus.domain.organisation_split import (
    OrganisationSplitCommand,
    OrganisationSplitConflict,
    OrganisationSplitImpact,
    OrganisationSplitPlan,
)
from coeus.persistence import organisation_merge_postgres as merge
from coeus.persistence import organisation_split_postgres as split
from test_organisation_merge import _fixture as merge_fixture
from test_organisation_split import _fixture as split_fixture

NOW = datetime(2026, 8, 4, 11, tzinfo=UTC)


class _Result:
    def __init__(self, *, rows: tuple[dict[str, object], ...] = (), scalar: object = None) -> None:
        self.rows = rows
        self.scalar = scalar

    def mappings(self) -> "_Result":
        return self

    def first(self) -> object:
        return self.rows[0] if self.rows else None

    def one(self) -> object:
        return self.rows[0] if self.rows else {}

    def scalar_one_or_none(self) -> object:
        return self.scalar

    def all(self) -> list[object]:
        return list(self.rows)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.rows)


class _Connection:
    def __init__(self, *results: _Result) -> None:
        self.results = list(results)

    def execute(self, *_args: object, **_kwargs: object) -> _Result:
        return self.results.pop(0) if self.results else _Result()


class _Begin:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    def __enter__(self) -> _Connection:
        return self.connection

    def __exit__(self, *_args: object) -> None:
        return None


class _Engine:
    def __init__(self, connection: _Connection | None = None) -> None:
        self.connection = connection or _Connection()

    def begin(self) -> _Begin:
        return _Begin(self.connection)


def _merge_command() -> tuple[OrganisationMergeCommand, OrganisationMergeImpact]:
    actor, _sources, _successor, _grants, request, impact, dispositions = merge_fixture()
    return (
        OrganisationMergeCommand(
            uuid4(),
            "merge-branch-guard",
            actor,
            OrganisationMergePlan(request, dispositions),
            "a" * 64,
        ),
        impact,
    )


def _merge_rows(command: OrganisationMergeCommand) -> tuple[dict[str, object], ...]:
    request = command.plan.request
    return tuple(
        {
            "unit_id": item.unit_id,
            "version": item.expected_version,
            "is_active": True,
            "parent_unit_id": uuid4(),
        }
        for item in (*request.sources, request.successor)
    )


@pytest.mark.parametrize("change", ("missing", "inactive", "version", "root"))
def test_merge_rejects_changed_units(change: str) -> None:
    command, _ = _merge_command()
    rows = list(_merge_rows(command))
    if change == "missing":
        rows.pop()
    elif change == "inactive":
        rows[0]["is_active"] = False
    elif change == "version":
        rows[0]["version"] = 2
    else:
        rows[0]["parent_unit_id"] = None
    connection = cast(Connection, _Connection(_Result(rows=tuple(rows))))
    with pytest.raises(OrganisationMergeConflict):
        merge._validate_units_and_authority(connection, command, NOW)


@pytest.mark.parametrize(("nested", "message"), ((True, "inside"), (False, "cannot overlap")))
def test_merge_rejects_nested_successor_and_overlapping_sources(nested: bool, message: str) -> None:
    command, _ = _merge_command()
    marker = _Result(rows=({},))
    connection = cast(
        Connection,
        _Connection(
            _Result(rows=_merge_rows(command)),
            marker if nested else _Result(),
            _Result() if nested else marker,
        ),
    )
    with pytest.raises(OrganisationMergeConflict, match=message):
        merge._validate_units_and_authority(connection, command, NOW)


def test_merge_finish_requires_every_source() -> None:
    command, _ = _merge_command()
    with pytest.raises(OrganisationMergeConflict, match="source unit changed"):
        merge._finish_units(cast(Connection, _Connection(_Result(rows=()))), command, NOW)


def test_merge_finish_requires_current_successor() -> None:
    command, _ = _merge_command()
    rows = tuple(
        {"unit_id": item.unit_id, "version": item.expected_version + 1}
        for item in command.plan.request.sources
    )
    connection = cast(Connection, _Connection(_Result(rows=rows), _Result(scalar=None)))
    with pytest.raises(OrganisationMergeConflict, match="successor unit changed"):
        merge._finish_units(connection, command, NOW)


def test_merge_replay_rejects_colliding_rows() -> None:
    command, _ = _merge_command()
    with pytest.raises(merge.OrganisationMergeIdempotencyConflict):
        merge._replay((cast(object, {}), cast(object, {})), command)  # type: ignore[arg-type]


def _patch_merge_apply(
    monkeypatch: pytest.MonkeyPatch,
    impact: OrganisationMergeImpact,
    *,
    expected_hash: str = "a" * 64,
) -> merge.PostgresOrganisationMergeStore:
    monkeypatch.setattr(merge, "_advisory_locks", lambda *_: None)
    monkeypatch.setattr(merge, "_load_command", lambda *_: ())
    monkeypatch.setattr(merge, "_lock_units", lambda *_: None)
    monkeypatch.setattr(merge, "lock_merge_records", lambda *_: None)
    monkeypatch.setattr(merge, "transaction_time", lambda *_: NOW)
    monkeypatch.setattr(merge, "_validate_units_and_authority", lambda *_: None)
    monkeypatch.setattr(merge, "inspect_merge", lambda *_: impact)
    monkeypatch.setattr(merge, "validate_merge_dispositions", lambda *_: None)
    monkeypatch.setattr(merge, "merge_hash", lambda *_: expected_hash)
    return merge.PostgresOrganisationMergeStore(_Engine())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("changes", "expected_hash", "message"),
    (
        ({}, "b" * 64, "preview is stale"),
        ({"maximum_result_depth": 13}, "a" * 64, "maximum depth"),
        ({"newly_covering_grants": 1}, "a" * 64, "broaden"),
        ({"reservations": 1}, "a" * 64, "unsupported dependent"),
        ({"team_calendar_events": 1}, "a" * 64, "unsupported dependent"),
        ({"saved_views": 1}, "a" * 64, "unsupported dependent"),
    ),
)
def test_merge_apply_rechecks_preview_and_unsupported_impacts(
    monkeypatch: pytest.MonkeyPatch,
    changes: dict[str, object],
    expected_hash: str,
    message: str,
) -> None:
    command, impact = _merge_command()
    impact = replace(impact, **changes)
    store = _patch_merge_apply(monkeypatch, impact, expected_hash=expected_hash)
    with pytest.raises(OrganisationMergeConflict, match=message):
        store._apply_once(command)


def _split_command() -> tuple[OrganisationSplitCommand, OrganisationSplitImpact]:
    actor, _parent, _source, _grants, request, impact, dispositions = split_fixture()
    return (
        OrganisationSplitCommand(
            uuid4(),
            "split-branch-guard",
            actor,
            OrganisationSplitPlan(request, dispositions),
            "a" * 64,
        ),
        impact,
    )


@pytest.mark.parametrize("change", ("missing", "inactive", "parent", "version"))
def test_split_rejects_changed_source_or_parent(change: str) -> None:
    command, _ = _split_command()
    request = command.plan.request
    rows = [
        {
            "unit_id": request.source.unit_id,
            "version": 1,
            "is_active": True,
            "parent_unit_id": request.parent.unit_id,
        },
        {
            "unit_id": request.parent.unit_id,
            "version": 1,
            "is_active": True,
            "parent_unit_id": uuid4(),
        },
    ]
    if change == "missing":
        rows.pop()
    elif change == "inactive":
        rows[0]["is_active"] = False
    elif change == "parent":
        rows[0]["parent_unit_id"] = uuid4()
    else:
        rows[1]["version"] = 2
    with pytest.raises(OrganisationSplitConflict, match="source or parent changed"):
        split._validate_units_and_authority(
            cast(Connection, _Connection(_Result(rows=tuple(rows)))), command, NOW
        )


@pytest.mark.parametrize("field", ("reservations", "team_calendar_events", "saved_views"))
def test_split_apply_rejects_unsupported_dependencies(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    command, impact = _split_command()
    impact = replace(impact, **{field: 1})
    monkeypatch.setattr(split, "_locks", lambda *_: None)
    monkeypatch.setattr(split, "_load_command", lambda *_: ())
    monkeypatch.setattr(split, "lock_split_records", lambda *_: None)
    monkeypatch.setattr(split, "transaction_time", lambda *_: NOW)
    monkeypatch.setattr(split, "_validate_units_and_authority", lambda *_: None)
    monkeypatch.setattr(split, "inspect_split", lambda *_: impact)
    monkeypatch.setattr(split, "validate_split_dispositions", lambda *_: None)
    monkeypatch.setattr(split, "split_hash", lambda *_: command.preview_hash)
    store = split.PostgresOrganisationSplitStore(_Engine())  # type: ignore[arg-type]
    with pytest.raises(OrganisationSplitConflict, match="unsupported dependent"):
        store._apply_once(command)


def test_split_apply_rejects_stale_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    command, impact = _split_command()
    monkeypatch.setattr(split, "_locks", lambda *_: None)
    monkeypatch.setattr(split, "_load_command", lambda *_: ())
    monkeypatch.setattr(split, "lock_split_records", lambda *_: None)
    monkeypatch.setattr(split, "transaction_time", lambda *_: NOW)
    monkeypatch.setattr(split, "_validate_units_and_authority", lambda *_: None)
    monkeypatch.setattr(split, "inspect_split", lambda *_: impact)
    monkeypatch.setattr(split, "validate_split_dispositions", lambda *_: None)
    monkeypatch.setattr(split, "split_hash", lambda *_: "b" * 64)
    store = split.PostgresOrganisationSplitStore(_Engine())  # type: ignore[arg-type]
    with pytest.raises(OrganisationSplitConflict, match="preview is stale"):
        store._apply_once(command)
