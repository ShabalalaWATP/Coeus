"""Policy tests for explicit-mapping organisation splits."""

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
    MergeUnitVersion,
)
from coeus.domain.organisation_split import (
    OrganisationSplitCommand,
    OrganisationSplitConflict,
    OrganisationSplitDenied,
    OrganisationSplitImpact,
    OrganisationSplitPlan,
    OrganisationSplitRequest,
    OrganisationSplitResult,
    SplitSuccessor,
)
from coeus.services.organisation_split import OrganisationSplitService

NOW = datetime(2026, 8, 3, 20, tzinfo=UTC)


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
    def __init__(self, impact: OrganisationSplitImpact) -> None:
        self.impact = impact
        self.replayed: OrganisationSplitResult | None = None

    def inspect(self, request: OrganisationSplitRequest) -> OrganisationSplitImpact:
        return self.impact

    def replay(self, command: OrganisationSplitCommand):  # type: ignore[no-untyped-def]
        return self.replayed

    def apply(self, command: OrganisationSplitCommand) -> OrganisationSplitResult:
        request = command.plan.request
        return OrganisationSplitResult(
            replace(request.source, expected_version=request.source.expected_version + 1),
            replace(request.parent, expected_version=request.parent.expected_version + 1),
            tuple(MergeUnitVersion(item.unit_id, 1) for item in request.successors),
        )


def _fixture():  # type: ignore[no-untyped-def]
    actor_id, grandparent_id = uuid4(), uuid4()
    parent = OrganisationUnit(
        uuid4(), "Parent", "Parent", OrganisationCategory.BRANCH, grandparent_id, NOW
    )
    source = OrganisationUnit(
        uuid4(), "Source", "Source", OrganisationCategory.DELIVERY_TEAM, parent.unit_id, NOW
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
            "Synthetic split authority.",
        )
        for unit in (source, parent)
    )
    successors = tuple(
        SplitSuccessor(uuid4(), name, name, OrganisationCategory.DELIVERY_TEAM, "Europe/London")
        for name in ("Red", "Blue")
    )
    request = OrganisationSplitRequest(
        MergeUnitVersion(source.unit_id, 1),
        MergeUnitVersion(parent.unit_id, 1),
        successors,
        grants[0].grant_id,
        grants[1].grant_id,
        "Split the synthetic delivery team.",
    )
    membership = MergeAffectedRecord(MergeRecordKind.MEMBERSHIP, uuid4(), source.unit_id, 2)
    task = MergeAffectedRecord(MergeRecordKind.TASK, uuid4(), source.unit_id, 3)
    impact = OrganisationSplitImpact((membership, task), 0, 0, 0, "a" * 64)
    dispositions = (
        MergeDisposition(
            membership.kind,
            membership.record_id,
            membership.version,
            MergeDispositionAction.MOVE,
            successors[0].unit_id,
            uuid4(),
        ),
        MergeDisposition(
            task.kind,
            task.record_id,
            task.version,
            MergeDispositionAction.MOVE,
            successors[1].unit_id,
        ),
    )
    return actor_id, parent, source, grants, request, impact, dispositions


def test_assess_preview_execute_and_replay() -> None:
    actor_id, parent, source, grants, request, impact, dispositions = _fixture()
    store = _Store(impact)
    service = OrganisationSplitService(  # type: ignore[arg-type]
        _Organisation((parent, source), grants), store, clock=lambda: NOW
    )
    preview = service.preview(OrganisationSplitPlan(request, dispositions), actor_id)
    command = OrganisationSplitCommand(
        uuid4(), "split-source", actor_id, preview.plan, preview.preview_hash
    )
    assert service.execute(command).source.expected_version == 2
    store.replayed = OrganisationSplitResult(request.source, request.parent, (), True)
    assert service.execute(command).replayed
    store.replayed = None
    with pytest.raises(OrganisationSplitConflict, match="preview"):
        service.execute(replace(command, preview_hash="b" * 64))


@pytest.mark.parametrize(
    "change", ("missing", "inactive", "root", "source_version", "parent", "parent_version")
)
def test_assess_rejects_invalid_units(change: str) -> None:
    actor_id, parent, source, grants, request, impact, _ = _fixture()
    units = [parent, source]
    if change == "missing":
        units.pop()
    elif change == "inactive":
        units[1] = replace(source, is_active=False)
    elif change == "root":
        units[1] = replace(source, parent_unit_id=None)
    elif change == "source_version":
        units[1] = replace(source, version=2)
    elif change == "parent":
        units[1] = replace(source, parent_unit_id=uuid4())
    elif change == "parent_version":
        units[0] = replace(parent, version=2)
    with pytest.raises(OrganisationSplitConflict):
        OrganisationSplitService(  # type: ignore[arg-type]
            _Organisation(units, grants), _Store(impact), clock=lambda: NOW
        ).assess(request, actor_id)


def test_assess_rejects_authority_and_unhandled_dependencies() -> None:
    actor_id, parent, source, grants, request, impact, _ = _fixture()
    with pytest.raises(OrganisationSplitDenied):
        OrganisationSplitService(  # type: ignore[arg-type]
            _Organisation((parent, source), grants[1:]), _Store(impact), clock=lambda: NOW
        ).assess(request, actor_id)
    for blocked in (
        replace(impact, reservations=1),
        replace(impact, team_calendar_events=1),
        replace(impact, saved_views=1),
    ):
        with pytest.raises(OrganisationSplitConflict):
            OrganisationSplitService(  # type: ignore[arg-type]
                _Organisation((parent, source), grants), _Store(blocked), clock=lambda: NOW
            ).assess(request, actor_id)


def test_dispositions_must_be_complete_current_and_kind_safe() -> None:
    actor_id, parent, source, grants, request, impact, dispositions = _fixture()
    service = OrganisationSplitService(  # type: ignore[arg-type]
        _Organisation((parent, source), grants), _Store(impact), clock=lambda: NOW
    )
    invalid = (
        dispositions[:1],
        (*dispositions, dispositions[0]),
        (replace(dispositions[0], expected_version=9), dispositions[1]),
        (replace(dispositions[0], action=MergeDispositionAction.CANCEL), dispositions[1]),
        (replace(dispositions[0], target_unit_id=uuid4()), dispositions[1]),
        (replace(dispositions[0], replacement_id=None), dispositions[1]),
        (dispositions[0], replace(dispositions[1], replacement_id=uuid4())),
        (dispositions[0], replace(dispositions[1], action=MergeDispositionAction.END)),
    )
    for values in invalid:
        with pytest.raises(OrganisationSplitConflict):
            service.preview(OrganisationSplitPlan(request, values), actor_id)


def test_capability_must_follow_profile_target_and_action() -> None:
    actor_id, parent, source, grants, request, _, _ = _fixture()
    profile = MergeAffectedRecord(MergeRecordKind.DELIVERY_PROFILE, uuid4(), source.unit_id, 1)
    capability = MergeAffectedRecord(
        MergeRecordKind.CAPABILITY, uuid4(), source.unit_id, 1, profile.record_id
    )
    impact = OrganisationSplitImpact((profile, capability), 0, 0, 0, "c" * 64)
    profile_move = MergeDisposition(
        profile.kind,
        profile.record_id,
        1,
        MergeDispositionAction.MOVE,
        request.successors[0].unit_id,
    )
    capability_move = replace(profile_move, kind=capability.kind, record_id=capability.record_id)
    service = OrganisationSplitService(  # type: ignore[arg-type]
        _Organisation((parent, source), grants), _Store(impact), clock=lambda: NOW
    )
    service.preview(OrganisationSplitPlan(request, (profile_move, capability_move)), actor_id)
    with pytest.raises(OrganisationSplitConflict, match="follow"):
        service.preview(
            OrganisationSplitPlan(
                request,
                (
                    profile_move,
                    replace(capability_move, target_unit_id=request.successors[1].unit_id),
                ),
            ),
            actor_id,
        )
    missing = replace(impact, records=(profile, replace(capability, container_id=None)))
    with pytest.raises(OrganisationSplitConflict, match="missing"):
        OrganisationSplitService(  # type: ignore[arg-type]
            _Organisation((parent, source), grants), _Store(missing), clock=lambda: NOW
        ).preview(OrganisationSplitPlan(request, (profile_move, capability_move)), actor_id)


def test_delivery_records_cannot_move_to_structural_successors() -> None:
    actor_id, parent, source, grants, request, impact, dispositions = _fixture()
    structural = replace(request.successors[0], category=OrganisationCategory.BRANCH)
    request = replace(request, successors=(structural, request.successors[1]))
    service = OrganisationSplitService(  # type: ignore[arg-type]
        _Organisation((parent, source), grants), _Store(impact), clock=lambda: NOW
    )
    with pytest.raises(OrganisationSplitConflict, match="delivery team"):
        service.preview(OrganisationSplitPlan(request, dispositions), actor_id)


def test_split_records_validate_shapes() -> None:
    actor_id, _, _, _, request, impact, _ = _fixture()
    with pytest.raises(ValueError, match="two distinct"):
        replace(request, successors=request.successors[:1])
    with pytest.raises(ValueError, match="identities"):
        replace(request, source=replace(request.source, unit_id=request.parent.unit_id))
    with pytest.raises(ValueError, match="names"):
        replace(
            request, successors=(request.successors[0], replace(request.successors[1], name="RED"))
        )
    with pytest.raises(ValueError, match="unique"):
        replace(impact, records=(impact.records[0], impact.records[0]))
    with pytest.raises(ValueError, match="counts"):
        replace(impact, reservations=-1)
    with pytest.raises(ValueError, match="state_digest"):
        replace(impact, state_digest="invalid")
    for key in ("", " key", "x" * 129, "bad\nkey"):
        with pytest.raises(ValueError):
            OrganisationSplitCommand(
                uuid4(), key, actor_id, OrganisationSplitPlan(request, ()), "a" * 64
            )
