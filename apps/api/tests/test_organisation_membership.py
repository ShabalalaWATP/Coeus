"""Policy tests for single-home organisation membership commands."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from coeus.domain.auth import UserAccount
from coeus.domain.organisation import (
    ManagementAction,
    MembershipRole,
    OrganisationCategory,
    OrganisationManagementGrant,
    OrganisationUnit,
)
from coeus.domain.organisation_membership import (
    MembershipCommandConflict,
    MembershipCommandDenied,
    MembershipMutationCommand,
    MembershipMutationRequest,
    MembershipMutationResult,
    MembershipMutationSnapshot,
    MembershipOperation,
)
from coeus.services.organisation_membership import OrganisationMembershipService

NOW = datetime(2026, 8, 3, 13, tzinfo=UTC)


class _Organisation:
    def __init__(
        self, unit: OrganisationUnit | None, grant: OrganisationManagementGrant | None
    ) -> None:
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


class _Users:
    def __init__(self, user: UserAccount | None) -> None:
        self.user = user

    def get_user(self, user_id: UUID) -> UserAccount | None:
        return self.user if self.user is not None and self.user.user_id == user_id else None


class _Store:
    def __init__(self, snapshot: MembershipMutationSnapshot) -> None:
        self.snapshot = snapshot
        self.replayed: MembershipMutationResult | None = None
        self.applied: MembershipMutationCommand | None = None

    def inspect(self, request: MembershipMutationRequest) -> MembershipMutationSnapshot:
        return self.snapshot

    def replay(self, command: MembershipMutationCommand):  # type: ignore[no-untyped-def]
        return self.replayed

    def apply(self, command: MembershipMutationCommand) -> MembershipMutationResult:
        self.applied = command
        return MembershipMutationResult(command.request.membership_id, 1)


def _fixture():  # type: ignore[no-untyped-def]
    actor_id, user_id, unit_id = uuid4(), uuid4(), uuid4()
    user = UserAccount(user_id, "analyst1", "Analyst One", frozenset(), frozenset(), "x", True, 3)
    unit = OrganisationUnit(
        unit_id,
        "Synthetic Delivery",
        "Delivery",
        OrganisationCategory.DELIVERY_TEAM,
        uuid4(),
        NOW - timedelta(days=1),
    )
    grant = OrganisationManagementGrant(
        uuid4(),
        actor_id,
        unit_id,
        ManagementAction.ROSTER_MANAGE,
        False,
        NOW - timedelta(days=1),
        actor_id,
        "Synthetic roster authority",
    )
    request = MembershipMutationRequest(
        MembershipOperation.CREATE,
        uuid4(),
        user_id,
        unit_id,
        0,
        MembershipRole.MEMBER,
        True,
        NOW,
        None,
        grant.grant_id,
        "Create the synthetic home membership.",
    )
    snapshot = MembershipMutationSnapshot(unit.version, 0, 0, "a" * 64)
    return actor_id, user, unit, grant, request, snapshot


def test_membership_preview_execute_and_replay() -> None:
    actor_id, user, unit, grant, request, snapshot = _fixture()
    store = _Store(snapshot)
    service = OrganisationMembershipService(  # type: ignore[arg-type]
        _Organisation(unit, grant), _Users(user), store, clock=lambda: NOW
    )
    preview = service.preview(request, actor_id)
    command = MembershipMutationCommand(
        uuid4(), "create-analyst-home", actor_id, request, preview.preview_hash
    )
    assert service.execute(command).version == 1
    assert store.applied == command
    store.replayed = MembershipMutationResult(request.membership_id, 1, True)
    assert service.execute(command).replayed
    store.replayed = None
    with pytest.raises(MembershipCommandConflict, match="preview"):
        service.execute(replace(command, preview_hash="b" * 64))


def test_preview_rejects_inactive_identity_scope_and_stale_state() -> None:
    actor_id, user, unit, grant, request, snapshot = _fixture()
    with pytest.raises(MembershipCommandConflict, match="account"):
        OrganisationMembershipService(  # type: ignore[arg-type]
            _Organisation(unit, grant), _Users(replace(user, is_active=False)), _Store(snapshot)
        ).preview(request, actor_id)
    with pytest.raises(MembershipCommandConflict, match="unit"):
        OrganisationMembershipService(  # type: ignore[arg-type]
            _Organisation(replace(unit, is_active=False), grant), _Users(user), _Store(snapshot)
        ).preview(request, actor_id)
    with pytest.raises(MembershipCommandDenied):
        OrganisationMembershipService(  # type: ignore[arg-type]
            _Organisation(unit, None), _Users(user), _Store(snapshot), clock=lambda: NOW
        ).preview(request, actor_id)
    service = OrganisationMembershipService(  # type: ignore[arg-type]
        _Organisation(unit, grant),
        _Users(user),
        _Store(replace(snapshot, unit_version=2)),
        clock=lambda: NOW,
    )
    with pytest.raises(MembershipCommandConflict, match="unit version"):
        service.preview(request, actor_id)
    service._store.snapshot = replace(snapshot, current_membership_version=1)  # type: ignore[union-attr]
    with pytest.raises(MembershipCommandConflict, match="membership version"):
        service.preview(request, actor_id)


def test_preview_rejects_invalid_assignment_and_future_end() -> None:
    actor_id, user, unit, grant, request, snapshot = _fixture()
    branch = replace(unit, category=OrganisationCategory.BRANCH)
    with pytest.raises(MembershipCommandConflict, match="delivery"):
        OrganisationMembershipService(  # type: ignore[arg-type]
            _Organisation(branch, grant), _Users(user), _Store(snapshot), clock=lambda: NOW
        ).preview(request, actor_id)
    end = replace(
        request,
        operation=MembershipOperation.END,
        expected_version=1,
        assignment_eligible=False,
        valid_until=NOW + timedelta(days=1),
    )
    with pytest.raises(MembershipCommandConflict, match="future"):
        OrganisationMembershipService(  # type: ignore[arg-type]
            _Organisation(unit, grant), _Users(user), _Store(snapshot), clock=lambda: NOW
        ).preview(end, actor_id)


def test_membership_records_validate_command_shapes() -> None:
    actor_id, _, _, _, request, snapshot = _fixture()
    with pytest.raises(ValueError, match="zero"):
        replace(request, expected_version=1)
    with pytest.raises(ValueError, match="positive"):
        replace(request, operation=MembershipOperation.UPDATE)
    with pytest.raises(ValueError, match="requires"):
        replace(
            request,
            operation=MembershipOperation.END,
            expected_version=1,
            assignment_eligible=False,
        )
    with pytest.raises(ValueError, match="only end"):
        replace(request, valid_until=NOW + timedelta(days=1))
    with pytest.raises(ValueError, match="follow"):
        replace(
            request,
            operation=MembershipOperation.END,
            expected_version=1,
            assignment_eligible=False,
            valid_until=NOW,
        )
    with pytest.raises(ValueError, match="eligible"):
        replace(
            request,
            operation=MembershipOperation.END,
            expected_version=1,
            valid_until=NOW + timedelta(days=1),
        )
    with pytest.raises(ValueError, match="versions"):
        replace(snapshot, current_membership_version=-1)
    with pytest.raises(ValueError, match="active_task_legs"):
        replace(snapshot, active_task_legs=-1)
    with pytest.raises(ValueError, match="state_digest"):
        replace(snapshot, state_digest="invalid")
    for key in ("", " key", "x" * 129, "bad\nkey"):
        with pytest.raises(ValueError):
            MembershipMutationCommand(uuid4(), key, actor_id, request, "a" * 64)
