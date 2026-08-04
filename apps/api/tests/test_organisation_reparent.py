"""Policy tests for previewed organisation reparenting."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from coeus.domain.organisation import (
    ManagementAction,
    OrganisationCategory,
    OrganisationManagementGrant,
    OrganisationUnit,
)
from coeus.domain.organisation_reparent import (
    OrganisationReparentCommand,
    OrganisationReparentConflict,
    OrganisationReparentDenied,
    OrganisationReparentImpact,
    OrganisationReparentRequest,
    OrganisationReparentResult,
)
from coeus.services.organisation_reparent import OrganisationReparentService

NOW = datetime(2026, 8, 3, 12, tzinfo=UTC)


class _Organisation:
    def __init__(
        self, units: tuple[OrganisationUnit, ...], grants: tuple[OrganisationManagementGrant, ...]
    ) -> None:
        self.units = {unit.unit_id: unit for unit in units}
        self.grants = {grant.grant_id: grant for grant in grants}

    def get_unit(self, unit_id: UUID):  # type: ignore[no-untyped-def]
        return self.units.get(unit_id)

    def effective_grants(self, manager_id: UUID, at: datetime):  # type: ignore[no-untyped-def]
        return tuple(
            grant
            for grant in self.grants.values()
            if grant.manager_user_id == manager_id
            and grant.valid_from <= at
            and grant.revoked_at is None
        )

    def get_management_grant(self, grant_id: UUID):  # type: ignore[no-untyped-def]
        return self.grants.get(grant_id)

    def unit_is_within(self, root_id: UUID, target_id: UUID) -> bool:
        cursor = self.units.get(target_id)
        while cursor is not None:
            if cursor.unit_id == root_id:
                return True
            cursor = self.units.get(cursor.parent_unit_id)
        return False


class _Store:
    def __init__(self, impact: OrganisationReparentImpact) -> None:
        self.impact = impact
        self.replayed: OrganisationReparentResult | None = None
        self.applied: OrganisationReparentCommand | None = None

    def inspect(self, request: OrganisationReparentRequest) -> OrganisationReparentImpact:
        return self.impact

    def replay(self, command: OrganisationReparentCommand):  # type: ignore[no-untyped-def]
        return self.replayed

    def apply(self, command: OrganisationReparentCommand) -> OrganisationReparentResult:
        self.applied = command
        return OrganisationReparentResult(
            command.request.unit_id, command.request.new_parent_unit_id, 2, uuid4()
        )


def _foundation():  # type: ignore[no-untyped-def]
    root = _unit("Root", None)
    source_parent = _unit("Source", root.unit_id)
    source = _unit("Moved", source_parent.unit_id)
    target = _unit("Target", root.unit_id)
    actor_id = uuid4()
    grant = OrganisationManagementGrant(
        uuid4(),
        actor_id,
        root.unit_id,
        ManagementAction.ORGANISATION_REPARENT,
        True,
        NOW,
        actor_id,
        "Synthetic reparent authority",
    )
    request = OrganisationReparentRequest(
        source.unit_id,
        target.unit_id,
        source.version,
        target.version,
        grant.grant_id,
        "Move the synthetic unit.",
    )
    impact = OrganisationReparentImpact(
        source_parent.unit_id,
        uuid4(),
        1,
        2,
        1,
        3,
        4,
        0,
        0,
        0,
        0,
        0,
        3,
        "a" * 64,
    )
    return (root, source_parent, source, target), actor_id, grant, request, impact


def _unit(name: str, parent_id: UUID | None, *, active: bool = True) -> OrganisationUnit:
    return OrganisationUnit(
        uuid4(),
        name,
        name[:8],
        OrganisationCategory.BRANCH,
        parent_id,
        NOW,
        is_active=active,
    )


def test_preview_execute_and_replay_are_actor_and_impact_bound() -> None:
    units, actor_id, grant, request, impact = _foundation()
    store = _Store(impact)
    service = OrganisationReparentService(  # type: ignore[arg-type]
        _Organisation(units, (grant,)), store, clock=lambda: NOW
    )
    preview = service.preview(request, actor_id)
    assert preview.impact.descendants == 1
    command = OrganisationReparentCommand(
        uuid4(), "move-synthetic-unit", actor_id, request, preview.preview_hash
    )
    assert service.execute(command).parent_unit_id == request.new_parent_unit_id
    assert store.applied == command
    store.replayed = OrganisationReparentResult(
        request.unit_id, request.new_parent_unit_id, 2, uuid4(), True
    )
    assert service.execute(command).replayed
    store.replayed = None
    with pytest.raises(OrganisationReparentConflict, match="preview"):
        service.execute(replace(command, preview_hash="b" * 64))


@pytest.mark.parametrize(
    ("change", "message"),
    (
        ({"source_missing": True}, "not active"),
        ({"source_inactive": True}, "not active"),
        ({"source_root": True}, "root"),
        ({"source_version": True}, "version"),
        ({"target_missing": True}, "new parent unit is not active"),
        ({"target_inactive": True}, "new parent unit is not active"),
        ({"target_version": True}, "version"),
        ({"same_parent": True}, "already"),
        ({"cycle": True}, "cycle"),
    ),
)
def test_preview_rejects_invalid_topology(change: dict[str, bool], message: str) -> None:
    units, actor_id, grant, request, impact = _foundation()
    root, source_parent, source, target = units
    if change.get("source_missing"):
        units = (root, source_parent, target)
    if change.get("source_inactive"):
        units = (root, source_parent, replace(source, is_active=False), target)
    if change.get("source_root"):
        units = (root, source_parent, replace(source, parent_unit_id=None), target)
    if change.get("source_version"):
        units = (root, source_parent, replace(source, version=2), target)
    if change.get("target_missing"):
        units = (root, source_parent, source)
    if change.get("target_inactive"):
        units = (root, source_parent, source, replace(target, is_active=False))
    if change.get("target_version"):
        units = (root, source_parent, source, replace(target, version=2))
    if change.get("same_parent"):
        request = replace(request, new_parent_unit_id=source_parent.unit_id)
    if change.get("cycle"):
        child_target = replace(target, parent_unit_id=source.unit_id)
        units = (root, source_parent, source, child_target)
    service = OrganisationReparentService(  # type: ignore[arg-type]
        _Organisation(units, (grant,)), _Store(impact), clock=lambda: NOW
    )
    with pytest.raises(OrganisationReparentConflict, match=message):
        service.preview(request, actor_id)


def test_preview_rejects_authority_depth_scope_and_state_changes() -> None:
    units, actor_id, grant, request, impact = _foundation()
    with pytest.raises(OrganisationReparentDenied):
        OrganisationReparentService(  # type: ignore[arg-type]
            _Organisation(units, ()), _Store(impact), clock=lambda: NOW
        ).preview(request, actor_id)
    service = OrganisationReparentService(  # type: ignore[arg-type]
        _Organisation(units, (grant,)),
        _Store(replace(impact, maximum_result_depth=13)),
        clock=lambda: NOW,
    )
    with pytest.raises(OrganisationReparentConflict, match="depth"):
        service.preview(request, actor_id)
    service._store.impact = replace(impact, newly_covering_grants=1)  # type: ignore[union-attr]
    with pytest.raises(OrganisationReparentConflict, match="broaden"):
        service.preview(request, actor_id)
    service._store.impact = replace(  # type: ignore[union-attr]
        impact, source_parent_unit_id=uuid4()
    )
    with pytest.raises(OrganisationReparentConflict, match="changed"):
        service.preview(request, actor_id)


def test_reparent_records_validate_inputs() -> None:
    units, actor_id, grant, request, impact = _foundation()
    with pytest.raises(ValueError, match="itself"):
        replace(request, new_parent_unit_id=request.unit_id)
    with pytest.raises(ValueError, match="versions"):
        replace(request, expected_unit_version=0)
    with pytest.raises(ValueError):
        replace(request, reason="")
    with pytest.raises(ValueError, match="counts"):
        replace(impact, memberships=-1)
    with pytest.raises(ValueError, match="state_digest"):
        replace(impact, state_digest="invalid")
    for key in ("", " key", "x" * 129, "bad\nkey"):
        with pytest.raises(ValueError):
            OrganisationReparentCommand(uuid4(), key, actor_id, request, "a" * 64)
    with pytest.raises(ValueError, match="preview_hash"):
        OrganisationReparentCommand(uuid4(), "key", actor_id, request, "invalid")
    assert units and grant.action is ManagementAction.ORGANISATION_REPARENT
