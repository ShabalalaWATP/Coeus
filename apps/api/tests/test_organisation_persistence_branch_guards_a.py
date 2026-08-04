"""Branch guards for organisation lifecycle and reparent persistence."""

from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import Connection

from coeus.domain.organisation import OrganisationCategory
from coeus.domain.organisation_lifecycle import (
    OrganisationMutationCommand,
    OrganisationMutationConflict,
    OrganisationMutationOperation,
    OrganisationMutationRequest,
)
from coeus.domain.organisation_reparent import (
    OrganisationReparentCommand,
    OrganisationReparentConflict,
    OrganisationReparentImpact,
    OrganisationReparentRequest,
)
from coeus.persistence import organisation_lifecycle_postgres as lifecycle
from coeus.persistence import organisation_reparent_postgres as reparent

NOW = datetime(2026, 8, 4, 9, tzinfo=UTC)


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

    def scalar_one(self) -> object:
        return self.scalar

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


def _mutation(operation: OrganisationMutationOperation) -> OrganisationMutationCommand:
    parent_id = uuid4() if operation is OrganisationMutationOperation.CREATE else None
    request = OrganisationMutationRequest(
        operation,
        uuid4(),
        parent_id,
        1,
        "Synthetic Unit",
        "SYN",
        OrganisationCategory.DELIVERY_TEAM,
        "Europe/London",
        "Synthetic description",
        uuid4(),
        "Synthetic persistence guard.",
    )
    return OrganisationMutationCommand(uuid4(), "branch-guard", uuid4(), request, "a" * 64)


@pytest.mark.parametrize(
    ("parent", "existing", "depth", "message"),
    (
        (None, None, 0, "parent unit is not active"),
        ({"is_active": False, "version": 1}, None, 0, "parent unit is not active"),
        ({"is_active": True, "version": 2}, None, 0, "parent unit version is stale"),
        ({"is_active": True, "version": 1}, {"unit_id": uuid4()}, 0, "identity is already"),
        ({"is_active": True, "version": 1}, None, 12, "depth limit"),
    ),
)
def test_create_unit_rejects_each_stale_topology_guard(
    monkeypatch: pytest.MonkeyPatch,
    parent: dict[str, object] | None,
    existing: dict[str, object] | None,
    depth: int,
    message: str,
) -> None:
    command = _mutation(OrganisationMutationOperation.CREATE)
    rows = iter((parent, existing))
    monkeypatch.setattr(lifecycle, "_locked_unit", lambda *_: next(rows))
    monkeypatch.setattr(lifecycle, "_require_grant", lambda *_: None)
    connection = cast(Connection, _Connection(_Result(scalar=depth)))
    with pytest.raises(OrganisationMutationConflict, match=message):
        lifecycle._create_unit(connection, command, NOW)


@pytest.mark.parametrize(
    ("unit", "message"),
    (
        (None, "unit is not active"),
        ({"is_active": False, "version": 1, "category": "delivery_team"}, "not active"),
        ({"is_active": True, "version": 2, "category": "delivery_team"}, "version is stale"),
        ({"is_active": True, "version": 1, "category": "branch"}, "category requires"),
    ),
)
def test_edit_unit_rejects_identity_version_and_category_guards(
    monkeypatch: pytest.MonkeyPatch, unit: dict[str, object] | None, message: str
) -> None:
    command = _mutation(OrganisationMutationOperation.EDIT)
    monkeypatch.setattr(lifecycle, "_locked_unit", lambda *_: unit)
    with pytest.raises(OrganisationMutationConflict, match=message):
        lifecycle._edit_unit(cast(Connection, _Connection()), command, NOW)


def test_edit_unit_rejects_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    command = _mutation(OrganisationMutationOperation.EDIT)
    request = command.request
    monkeypatch.setattr(
        lifecycle,
        "_locked_unit",
        lambda *_: {
            "is_active": True,
            "version": 1,
            "category": request.category.value,
            "name": request.name,
            "short_name": request.short_name,
            "time_zone": request.time_zone,
            "description": request.description,
        },
    )
    monkeypatch.setattr(lifecycle, "_require_grant", lambda *_: None)
    with pytest.raises(OrganisationMutationConflict, match="does not change"):
        lifecycle._edit_unit(cast(Connection, _Connection()), command, NOW)


def _reparent_command() -> OrganisationReparentCommand:
    request = OrganisationReparentRequest(
        uuid4(), uuid4(), 1, 1, uuid4(), "Synthetic reparent guard."
    )
    return OrganisationReparentCommand(uuid4(), "reparent-guard", uuid4(), request, "a" * 64)


def _impact(**changes: object) -> OrganisationReparentImpact:
    values: dict[str, Any] = {
        "source_parent_unit_id": uuid4(),
        "source_topology_revision_id": uuid4(),
        "descendants": 0,
        "memberships": 0,
        "grants": 0,
        "capability_mappings": 0,
        "active_task_legs": 0,
        "reservations": 0,
        "team_calendar_events": 0,
        "saved_views": 0,
        "pending_transfers": 0,
        "newly_covering_grants": 0,
        "maximum_result_depth": 2,
        "state_digest": "a" * 64,
    }
    values.update(changes)
    return OrganisationReparentImpact(**values)


@pytest.mark.parametrize(
    ("source_change", "target_change", "message"),
    (
        ({"missing": True}, {}, "source unit cannot"),
        ({"is_active": False}, {}, "source unit cannot"),
        ({"parent_unit_id": None}, {}, "source unit cannot"),
        ({"version": 2}, {}, "unit version is stale"),
        ({}, {"missing": True}, "new parent unit is not active"),
        ({}, {"is_active": False}, "new parent unit is not active"),
        ({}, {"version": 2}, "parent unit version is stale"),
        ({"same_parent": True}, {}, "already has this parent"),
    ),
)
def test_reparent_rejects_stale_source_and_target(
    monkeypatch: pytest.MonkeyPatch,
    source_change: dict[str, object],
    target_change: dict[str, object],
    message: str,
) -> None:
    command = _reparent_command()
    request = command.request
    source: dict[str, object] | None = {
        "is_active": True,
        "parent_unit_id": uuid4(),
        "version": 1,
    }
    target: dict[str, object] | None = {"is_active": True, "version": 1}
    if source_change.pop("missing", False):
        source = None
    elif source is not None:
        source.update(source_change)
        if source.pop("same_parent", False):
            source["parent_unit_id"] = request.new_parent_unit_id
    if target_change.get("missing"):
        target = None
    elif target is not None:
        target.update(target_change)
    rows = iter((source, target))
    monkeypatch.setattr(reparent, "_unit", lambda *_: next(rows))
    with pytest.raises(OrganisationReparentConflict, match=message):
        reparent._validate_and_impact(cast(Connection, _Connection()), command, NOW)


@pytest.mark.parametrize(
    ("cycle", "impact", "message"),
    (
        (True, _impact(), "create a cycle"),
        (False, _impact(maximum_result_depth=13), "depth limit"),
        (False, _impact(newly_covering_grants=1), "broaden"),
    ),
)
def test_reparent_rejects_cycle_depth_and_grant_broadening(
    monkeypatch: pytest.MonkeyPatch,
    cycle: bool,
    impact: OrganisationReparentImpact,
    message: str,
) -> None:
    command = _reparent_command()
    rows = iter(
        (
            {"is_active": True, "parent_unit_id": uuid4(), "version": 1},
            {"is_active": True, "version": 1},
        )
    )
    monkeypatch.setattr(reparent, "_unit", lambda *_: next(rows))
    monkeypatch.setattr(reparent, "lock_lineages", lambda *_: None)
    monkeypatch.setattr(reparent, "validate_lineage", lambda *_: None)
    monkeypatch.setattr(reparent, "_impact", lambda *_: impact)
    connection = cast(Connection, _Connection(_Result(rows=({},) if cycle else ())))
    with pytest.raises(OrganisationReparentConflict, match=message):
        reparent._validate_and_impact(connection, command, NOW)


def test_reparent_impact_requires_complete_topology() -> None:
    command = _reparent_command()
    for row in (None, {"parent_unit_id": None, "revision_id": uuid4()}):
        result = _Result(rows=() if row is None else (row,))
        with pytest.raises(OrganisationReparentConflict, match="topology is incomplete"):
            reparent._impact(cast(Connection, _Connection(result)), command.request)


def test_reparent_move_requires_root_revision() -> None:
    command = _reparent_command()
    connection = cast(
        Connection,
        _Connection(_Result(), _Result(scalar=2), _Result(), _Result(), _Result(rows=())),
    )
    with pytest.raises(OrganisationReparentConflict, match="no topology revision"):
        reparent._move(connection, command, NOW)
