"""Policy tests for fail-closed organisation deactivation."""

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
from coeus.domain.organisation_deactivation import (
    OrganisationDeactivationCommand,
    OrganisationDeactivationConflict,
    OrganisationDeactivationDenied,
    OrganisationDeactivationImpact,
    OrganisationDeactivationRequest,
    OrganisationDeactivationResult,
)
from coeus.services.organisation_deactivation import OrganisationDeactivationService

NOW = datetime(2026, 8, 3, 15, tzinfo=UTC)


class _Organisation:
    def __init__(self, unit, grant):  # type: ignore[no-untyped-def]
        self.unit = unit
        self.grant = grant

    def get_unit(self, unit_id: UUID):  # type: ignore[no-untyped-def]
        return self.unit if self.unit is not None and self.unit.unit_id == unit_id else None

    def effective_grants(self, manager_id: UUID, at: datetime):  # type: ignore[no-untyped-def]
        return () if self.grant is None else (self.grant,)

    def get_management_grant(self, grant_id: UUID):  # type: ignore[no-untyped-def]
        return self.grant if self.grant is not None and self.grant.grant_id == grant_id else None

    def unit_is_within(self, root_id: UUID, target_id: UUID) -> bool:
        return root_id == target_id


class _Store:
    def __init__(self, impact: OrganisationDeactivationImpact) -> None:
        self.impact = impact
        self.replayed: OrganisationDeactivationResult | None = None

    def inspect(self, request: OrganisationDeactivationRequest) -> OrganisationDeactivationImpact:
        return self.impact

    def replay(self, command: OrganisationDeactivationCommand):  # type: ignore[no-untyped-def]
        return self.replayed

    def apply(self, command: OrganisationDeactivationCommand) -> OrganisationDeactivationResult:
        return OrganisationDeactivationResult(command.request.unit_id, 2)


def _fixture():  # type: ignore[no-untyped-def]
    actor_id = uuid4()
    unit = OrganisationUnit(
        uuid4(),
        "Synthetic Leaf",
        "Leaf",
        OrganisationCategory.BRANCH,
        uuid4(),
        NOW,
    )
    grant = OrganisationManagementGrant(
        uuid4(),
        actor_id,
        unit.unit_id,
        ManagementAction.ORGANISATION_RESTRUCTURE,
        False,
        NOW,
        actor_id,
        "Synthetic restructure authority",
    )
    request = OrganisationDeactivationRequest(
        unit.unit_id, unit.version, grant.grant_id, "Deactivate the empty synthetic leaf."
    )
    impact = OrganisationDeactivationImpact(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, "a" * 64)
    return actor_id, unit, grant, request, impact


def test_preview_execute_and_replay() -> None:
    actor_id, unit, grant, request, impact = _fixture()
    store = _Store(impact)
    service = OrganisationDeactivationService(  # type: ignore[arg-type]
        _Organisation(unit, grant), store, clock=lambda: NOW
    )
    preview = service.preview(request, actor_id)
    command = OrganisationDeactivationCommand(
        uuid4(), "deactivate-leaf", actor_id, request, preview.preview_hash
    )
    assert service.execute(command).version == 2
    store.replayed = OrganisationDeactivationResult(unit.unit_id, 2, True)
    assert service.execute(command).replayed
    store.replayed = None
    with pytest.raises(OrganisationDeactivationConflict, match="preview"):
        service.execute(replace(command, preview_hash="b" * 64))


@pytest.mark.parametrize(
    ("unit_change", "message"),
    (
        ({"missing": True}, "not active"),
        ({"is_active": False}, "not active"),
        ({"parent_unit_id": None}, "root"),
        ({"version": 2}, "version"),
    ),
)
def test_preview_rejects_invalid_unit(unit_change: dict[str, object], message: str) -> None:
    actor_id, unit, grant, request, impact = _fixture()
    changed = None if unit_change.pop("missing", False) else replace(unit, **unit_change)
    with pytest.raises(OrganisationDeactivationConflict, match=message):
        OrganisationDeactivationService(  # type: ignore[arg-type]
            _Organisation(changed, grant), _Store(impact), clock=lambda: NOW
        ).preview(request, actor_id)


def test_preview_rejects_missing_authority_and_dependent_records() -> None:
    actor_id, unit, grant, request, impact = _fixture()
    with pytest.raises(OrganisationDeactivationDenied):
        OrganisationDeactivationService(  # type: ignore[arg-type]
            _Organisation(unit, None), _Store(impact), clock=lambda: NOW
        ).preview(request, actor_id)
    blocked = replace(impact, memberships=1)
    assert blocked.blocking_count == 1
    with pytest.raises(OrganisationDeactivationConflict, match="dependent"):
        OrganisationDeactivationService(  # type: ignore[arg-type]
            _Organisation(unit, grant), _Store(blocked), clock=lambda: NOW
        ).preview(request, actor_id)


def test_deactivation_records_validate_shapes() -> None:
    actor_id, _, _, request, impact = _fixture()
    with pytest.raises(ValueError, match="positive"):
        replace(request, expected_version=0)
    with pytest.raises(ValueError, match="counts"):
        replace(impact, active_children=-1)
    with pytest.raises(ValueError, match="state_digest"):
        replace(impact, state_digest="invalid")
    for key in ("", " key", "x" * 129, "bad\nkey"):
        with pytest.raises(ValueError):
            OrganisationDeactivationCommand(uuid4(), key, actor_id, request, "a" * 64)
