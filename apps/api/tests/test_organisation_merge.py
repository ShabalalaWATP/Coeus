"""Policy tests for explicit-disposition organisation merges."""

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
from coeus.domain.organisation_merge import (
    MergeAffectedRecord,
    MergeDisposition,
    MergeDispositionAction,
    MergeRecordKind,
    MergeUnitAuthority,
    MergeUnitVersion,
    OrganisationMergeCommand,
    OrganisationMergeConflict,
    OrganisationMergeDenied,
    OrganisationMergeImpact,
    OrganisationMergePlan,
    OrganisationMergeRequest,
    OrganisationMergeResult,
)
from coeus.services.organisation_merge import OrganisationMergeService

NOW = datetime(2026, 8, 3, 18, tzinfo=UTC)


class _Organisation:
    def __init__(self, units, grants):  # type: ignore[no-untyped-def]
        self.units = {item.unit_id: item for item in units}
        self.grants = tuple(grants)

    def get_unit(self, unit_id: UUID):  # type: ignore[no-untyped-def]
        return self.units.get(unit_id)

    def effective_grants(self, manager_id: UUID, at: datetime):  # type: ignore[no-untyped-def]
        return tuple(item for item in self.grants if item.manager_user_id == manager_id)

    def get_management_grant(self, grant_id: UUID):  # type: ignore[no-untyped-def]
        return next((item for item in self.grants if item.grant_id == grant_id), None)

    def unit_is_within(self, root_id: UUID, target_id: UUID) -> bool:
        return root_id == target_id


class _Store:
    def __init__(self, impact: OrganisationMergeImpact) -> None:
        self.impact = impact
        self.replayed: OrganisationMergeResult | None = None

    def inspect(self, request: OrganisationMergeRequest) -> OrganisationMergeImpact:
        return self.impact

    def replay(self, command: OrganisationMergeCommand):  # type: ignore[no-untyped-def]
        return self.replayed

    def apply(self, command: OrganisationMergeCommand) -> OrganisationMergeResult:
        return OrganisationMergeResult(
            command.plan.request.successor.unit_id,
            command.plan.request.successor.expected_version + 1,
            tuple(
                replace(item, expected_version=item.expected_version + 1)
                for item in command.plan.request.sources
            ),
        )


def _fixture():  # type: ignore[no-untyped-def]
    actor_id, parent_id = uuid4(), uuid4()
    sources = tuple(
        OrganisationUnit(uuid4(), name, name, OrganisationCategory.DELIVERY_TEAM, parent_id, NOW)
        for name in ("Alpha", "Bravo")
    )
    successor = OrganisationUnit(
        uuid4(), "Combined", "Combined", OrganisationCategory.DELIVERY_TEAM, parent_id, NOW
    )
    grants = tuple(
        OrganisationManagementGrant(
            uuid4(),
            actor_id,
            unit.unit_id,
            ManagementAction.ORGANISATION_RESTRUCTURE,
            False,
            NOW,
            actor_id,
            "Synthetic restructure authority",
        )
        for unit in (*sources, successor)
    )
    request = OrganisationMergeRequest(
        tuple(MergeUnitVersion(item.unit_id, 1) for item in sources),
        MergeUnitVersion(successor.unit_id, 1),
        tuple(MergeUnitAuthority(item.root_unit_id, item.grant_id) for item in grants),
        "Combine two synthetic delivery teams.",
    )
    membership = MergeAffectedRecord(MergeRecordKind.MEMBERSHIP, uuid4(), sources[0].unit_id, 2)
    task = MergeAffectedRecord(MergeRecordKind.TASK, uuid4(), sources[1].unit_id, 3)
    impact = OrganisationMergeImpact((membership, task), 0, 0, 1, 0, 0, 0, False, "a" * 64)
    dispositions = (
        MergeDisposition(
            membership.kind,
            membership.record_id,
            membership.version,
            MergeDispositionAction.MOVE,
            successor.unit_id,
            uuid4(),
        ),
        MergeDisposition(
            task.kind,
            task.record_id,
            task.version,
            MergeDispositionAction.MOVE,
            successor.unit_id,
        ),
    )
    return actor_id, sources, successor, grants, request, impact, dispositions


def test_assess_preview_execute_and_replay() -> None:
    actor_id, sources, successor, grants, request, impact, dispositions = _fixture()
    store = _Store(impact)
    service = OrganisationMergeService(  # type: ignore[arg-type]
        _Organisation((*sources, successor), grants), store, clock=lambda: NOW
    )
    assert service.assess(request, actor_id) == impact
    preview = service.preview(OrganisationMergePlan(request, dispositions), actor_id)
    command = OrganisationMergeCommand(
        uuid4(), "merge-alpha-bravo", actor_id, preview.plan, preview.preview_hash
    )
    assert service.execute(command).source_versions[0].expected_version == 2
    store.replayed = OrganisationMergeResult(successor.unit_id, 2, request.sources, True)
    assert service.execute(command).replayed
    store.replayed = None
    with pytest.raises(OrganisationMergeConflict, match="preview"):
        service.execute(replace(command, preview_hash="b" * 64))


@pytest.mark.parametrize(
    "change", ("missing", "inactive", "version", "root", "descendant", "overlapping_sources")
)
def test_assess_rejects_invalid_topology(change: str) -> None:
    actor_id, sources, successor, grants, request, impact, _ = _fixture()
    units = [*sources, successor]
    if change == "missing":
        units.pop(0)
    elif change == "inactive":
        units[0] = replace(units[0], is_active=False)
    elif change == "version":
        units[0] = replace(units[0], version=2)
    elif change == "root":
        units[0] = replace(units[0], parent_unit_id=None)
    organisation = _Organisation(units, grants)
    if change == "descendant":
        organisation.unit_is_within = lambda root, target: root == sources[0].unit_id  # type: ignore[method-assign]
    elif change == "overlapping_sources":
        organisation.unit_is_within = (  # type: ignore[method-assign]
            lambda root, target: root == sources[0].unit_id and target == sources[1].unit_id
        )
    with pytest.raises(OrganisationMergeConflict):
        OrganisationMergeService(  # type: ignore[arg-type]
            organisation, _Store(impact), clock=lambda: NOW
        ).assess(request, actor_id)


def test_assess_rejects_missing_authority_and_unhandled_dependencies() -> None:
    actor_id, sources, successor, grants, request, impact, _ = _fixture()
    with pytest.raises(OrganisationMergeDenied):
        OrganisationMergeService(  # type: ignore[arg-type]
            _Organisation((*sources, successor), grants[1:]), _Store(impact), clock=lambda: NOW
        ).assess(request, actor_id)
    for blocked in (
        replace(impact, newly_covering_grants=1),
        replace(impact, maximum_result_depth=13),
        replace(impact, reservations=1),
        replace(impact, team_calendar_events=1),
        replace(impact, saved_views=1),
    ):
        with pytest.raises(OrganisationMergeConflict):
            OrganisationMergeService(  # type: ignore[arg-type]
                _Organisation((*sources, successor), grants), _Store(blocked), clock=lambda: NOW
            ).assess(request, actor_id)


def test_preview_requires_complete_current_valid_dispositions() -> None:
    actor_id, sources, successor, grants, request, impact, dispositions = _fixture()
    service = OrganisationMergeService(  # type: ignore[arg-type]
        _Organisation((*sources, successor), grants), _Store(impact), clock=lambda: NOW
    )
    invalid = (
        dispositions[:1],
        (*dispositions, dispositions[0]),
        (replace(dispositions[0], expected_version=9), dispositions[1]),
        (replace(dispositions[0], action=MergeDispositionAction.CANCEL), dispositions[1]),
        (replace(dispositions[0], target_unit_id=sources[0].unit_id), dispositions[1]),
        (replace(dispositions[0], replacement_id=None), dispositions[1]),
        (dispositions[0], replace(dispositions[1], replacement_id=uuid4())),
        (dispositions[0], replace(dispositions[1], action=MergeDispositionAction.CANCEL)),
    )
    for values in invalid:
        with pytest.raises(OrganisationMergeConflict):
            service.preview(OrganisationMergePlan(request, values), actor_id)


def test_profile_and_capability_dispositions_are_consistent() -> None:
    actor_id, sources, successor, grants, request, _, _ = _fixture()
    profile = MergeAffectedRecord(MergeRecordKind.DELIVERY_PROFILE, uuid4(), sources[0].unit_id, 1)
    capability = MergeAffectedRecord(
        MergeRecordKind.CAPABILITY, uuid4(), sources[0].unit_id, 1, profile.record_id
    )
    impact = OrganisationMergeImpact((profile, capability), 0, 0, 1, 0, 0, 0, False, "c" * 64)
    service = OrganisationMergeService(  # type: ignore[arg-type]
        _Organisation((*sources, successor), grants), _Store(impact), clock=lambda: NOW
    )
    profile_move = MergeDisposition(
        profile.kind, profile.record_id, 1, MergeDispositionAction.MOVE, successor.unit_id
    )
    capability_move = MergeDisposition(
        capability.kind,
        capability.record_id,
        1,
        MergeDispositionAction.MOVE,
        successor.unit_id,
    )
    plan = OrganisationMergePlan(request, (profile_move, capability_move))
    service.preview(plan, actor_id)
    with pytest.raises(OrganisationMergeConflict, match="capability"):
        service.preview(
            OrganisationMergePlan(
                request,
                (
                    profile_move,
                    replace(
                        capability_move,
                        action=MergeDispositionAction.END,
                        target_unit_id=None,
                    ),
                ),
            ),
            actor_id,
        )
    with pytest.raises(OrganisationMergeConflict, match="profiles"):
        OrganisationMergeService(  # type: ignore[arg-type]
            _Organisation((*sources, successor), grants),
            _Store(replace(impact, successor_has_delivery_profile=True)),
            clock=lambda: NOW,
        ).preview(plan, actor_id)
    missing_container = replace(impact, records=(profile, replace(capability, container_id=None)))
    with pytest.raises(OrganisationMergeConflict, match="missing"):
        OrganisationMergeService(  # type: ignore[arg-type]
            _Organisation((*sources, successor), grants),
            _Store(missing_container),
            clock=lambda: NOW,
        ).preview(plan, actor_id)


def test_merge_records_validate_shapes() -> None:
    actor_id, sources, _successor, _grants, request, impact, _ = _fixture()
    with pytest.raises(ValueError, match="two distinct"):
        replace(request, sources=(request.sources[0],))
    with pytest.raises(ValueError, match="successor"):
        replace(request, successor=request.sources[0])
    with pytest.raises(ValueError, match="authorities"):
        replace(request, authorities=request.authorities[:-1])
    with pytest.raises(ValueError, match="positive"):
        MergeUnitVersion(sources[0].unit_id, 0)
    with pytest.raises(ValueError, match="affected record version"):
        replace(impact.records[0], version=0)
    with pytest.raises(ValueError, match="expected_version"):
        MergeDisposition(
            MergeRecordKind.TASK,
            uuid4(),
            0,
            MergeDispositionAction.CANCEL,
        )
    with pytest.raises(ValueError, match="successor_version"):
        OrganisationMergeResult(request.successor.unit_id, 0, request.sources)
    with pytest.raises(ValueError, match="unique"):
        replace(impact, records=(impact.records[0], impact.records[0]))
    with pytest.raises(ValueError, match="counts"):
        replace(impact, reservations=-1)
    with pytest.raises(ValueError, match="state_digest"):
        replace(impact, state_digest="invalid")
    for key in ("", " key", "x" * 129, "bad\nkey"):
        with pytest.raises(ValueError):
            OrganisationMergeCommand(
                uuid4(), key, actor_id, OrganisationMergePlan(request, ()), "a" * 64
            )
