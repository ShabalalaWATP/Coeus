"""Policy tests for scheduled single-home personnel transfers."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from coeus.domain.auth import UserAccount
from coeus.domain.organisation import (
    ManagementAction,
    MembershipRole,
    MembershipState,
    OrganisationCategory,
    OrganisationManagementGrant,
    OrganisationUnit,
    TeamMembership,
)
from coeus.domain.organisation_transfer import (
    PersonnelTransferCommand,
    PersonnelTransferConflict,
    PersonnelTransferDenied,
    PersonnelTransferImpact,
    PersonnelTransferRequest,
    PersonnelTransferResult,
    PersonnelTransferStatus,
)
from coeus.services.organisation_transfer import OrganisationTransferService

NOW = datetime(2026, 8, 3, 14, tzinfo=UTC)


class _Organisation:
    def __init__(self, source, target, grant):  # type: ignore[no-untyped-def]
        self.source = source
        self.target = target
        self.grant = grant

    def list_memberships(self, user_id: UUID):  # type: ignore[no-untyped-def]
        return () if self.source is None else (self.source,)

    def get_unit(self, unit_id: UUID):  # type: ignore[no-untyped-def]
        return self.target if self.target is not None and self.target.unit_id == unit_id else None

    def effective_grants(self, manager_id: UUID, at: datetime):  # type: ignore[no-untyped-def]
        return () if self.grant is None else (self.grant,)

    def get_management_grant(self, grant_id: UUID):  # type: ignore[no-untyped-def]
        return self.grant if self.grant is not None and self.grant.grant_id == grant_id else None

    def unit_is_within(self, root_id: UUID, target_id: UUID) -> bool:
        return root_id in {self.source.unit_id, self.target.unit_id}  # type: ignore[union-attr]


class _Users:
    def __init__(self, user: UserAccount | None) -> None:
        self.user = user

    def get_user(self, user_id: UUID) -> UserAccount | None:
        return self.user if self.user is not None and self.user.user_id == user_id else None


class _Store:
    def __init__(self, impact: PersonnelTransferImpact) -> None:
        self.impact = impact
        self.replayed: PersonnelTransferResult | None = None
        self.due_commands: tuple[PersonnelTransferCommand, ...] = ()
        self.activation_error: Exception | None = None

    def inspect(self, request: PersonnelTransferRequest) -> PersonnelTransferImpact:
        return self.impact

    def replay(self, command: PersonnelTransferCommand):  # type: ignore[no-untyped-def]
        return self.replayed

    def apply(self, command: PersonnelTransferCommand) -> PersonnelTransferResult:
        return _result(command, PersonnelTransferStatus.PENDING)

    def due(self, effective_at: datetime, *, limit: int = 100):  # type: ignore[no-untyped-def]
        return self.due_commands[:limit]

    def activate(self, command: PersonnelTransferCommand) -> PersonnelTransferResult:
        if self.activation_error is not None:
            raise self.activation_error
        return _result(command, PersonnelTransferStatus.APPLIED)

    def block(
        self, command: PersonnelTransferCommand, failure_code: str
    ) -> PersonnelTransferResult:
        return replace(_result(command, PersonnelTransferStatus.BLOCKED), failure_code=failure_code)


def _result(
    command: PersonnelTransferCommand, status: PersonnelTransferStatus
) -> PersonnelTransferResult:
    return PersonnelTransferResult(
        command.command_id,
        command.request.source_membership_id,
        command.request.target_membership_id,
        status,
        command.request.expected_membership_version + (status is PersonnelTransferStatus.APPLIED),
        1 if status is PersonnelTransferStatus.APPLIED else 0,
    )


def _fixture():  # type: ignore[no-untyped-def]
    actor_id, user_id, source_id, target_id = uuid4(), uuid4(), uuid4(), uuid4()
    source = TeamMembership(
        uuid4(),
        user_id,
        source_id,
        MembershipRole.MEMBER,
        MembershipState.ACTIVE,
        True,
        NOW - timedelta(days=1),
        actor_id,
        "Synthetic source membership",
        "manual",
    )
    target = OrganisationUnit(
        target_id,
        "Target Delivery",
        "Target",
        OrganisationCategory.DELIVERY_TEAM,
        uuid4(),
        NOW - timedelta(days=2),
    )
    user = UserAccount(user_id, "analyst", "Analyst", frozenset(), frozenset(), "x", True, 3)
    grant = OrganisationManagementGrant(
        uuid4(),
        actor_id,
        source_id,
        ManagementAction.ROSTER_TRANSFER,
        True,
        NOW - timedelta(days=2),
        actor_id,
        "Synthetic transfer authority",
    )
    request = PersonnelTransferRequest(
        source.membership_id,
        uuid4(),
        user_id,
        source_id,
        target_id,
        source.version,
        target.version,
        MembershipRole.MEMBER,
        True,
        NOW + timedelta(days=1),
        grant.grant_id,
        grant.grant_id,
        "Transfer the synthetic analyst.",
    )
    impact = PersonnelTransferImpact(2, 0, 0, 0, "a" * 64)
    return actor_id, user, source, target, grant, request, impact


def _service(user, source, target, grant, store):  # type: ignore[no-untyped-def]
    return OrganisationTransferService(  # type: ignore[arg-type]
        _Organisation(source, target, grant), _Users(user), store, clock=lambda: NOW
    )


def test_preview_execute_replay_and_due_activation() -> None:
    actor_id, user, source, target, grant, request, impact = _fixture()
    store = _Store(impact)
    service = _service(user, source, target, grant, store)
    preview = service.preview(request, actor_id)
    command = PersonnelTransferCommand(
        uuid4(), "transfer-analyst", actor_id, request, preview.preview_hash
    )
    assert service.execute(command).status is PersonnelTransferStatus.PENDING
    store.replayed = replace(_result(command, PersonnelTransferStatus.PENDING), replayed=True)
    assert service.execute(command).replayed
    store.replayed = None
    store.due_commands = (command,)
    service._clock = lambda: request.effective_at  # type: ignore[method-assign]
    assert service.activate_due()[0].status is PersonnelTransferStatus.APPLIED
    service._users.user = replace(user, is_active=False)  # type: ignore[union-attr]
    result = service.activate_due()[0]
    assert result.failure_code == "account_inactive"


def test_due_activation_blocks_lost_authority_and_changed_state() -> None:
    actor_id, user, source, target, grant, request, impact = _fixture()
    store = _Store(impact)
    service = _service(user, source, target, grant, store)
    preview = service.preview(request, actor_id)
    command = PersonnelTransferCommand(
        uuid4(), "transfer-block", actor_id, request, preview.preview_hash
    )
    store.due_commands = (command,)
    store.activation_error = PersonnelTransferDenied("lost")
    service._clock = lambda: request.effective_at  # type: ignore[method-assign]
    assert service.activate_due()[0].failure_code == "authority_lost"
    store.activation_error = PersonnelTransferConflict("changed")
    assert service.activate_due()[0].failure_code == "state_changed"
    with pytest.raises(ValueError, match="limit"):
        service.activate_due(limit=0)


@pytest.mark.parametrize(
    ("change", "message"),
    (
        ({"inactive_user": True}, "account"),
        ({"missing_source": True}, "source"),
        ({"stale_source": True}, "source"),
        ({"inactive_target": True}, "target"),
        ({"stale_target": True}, "version"),
        ({"past": True}, "future"),
        ({"wrong_category": True}, "delivery"),
        ({"no_grant": True}, "grant"),
    ),
)
def test_preview_rejects_invalid_transfer(change: dict[str, bool], message: str) -> None:
    actor_id, user, source, target, grant, request, impact = _fixture()
    if change.get("inactive_user"):
        user = replace(user, is_active=False)
    if change.get("missing_source"):
        source = None
    if change.get("stale_source"):
        source = replace(source, version=2)
    if change.get("inactive_target"):
        target = replace(target, is_active=False)
    if change.get("stale_target"):
        target = replace(target, version=2)
    if change.get("past"):
        request = replace(request, effective_at=NOW - timedelta(hours=1))
    if change.get("wrong_category"):
        target = replace(target, category=OrganisationCategory.BRANCH)
    if change.get("no_grant"):
        grant = None
    error = PersonnelTransferDenied if change.get("no_grant") else PersonnelTransferConflict
    with pytest.raises(error, match=message):
        _service(user, source, target, grant, _Store(impact)).preview(request, actor_id)


def test_transfer_records_validate_shapes() -> None:
    actor_id, _, _, _, _, request, impact = _fixture()
    with pytest.raises(ValueError, match="identities"):
        replace(request, target_membership_id=request.source_membership_id)
    with pytest.raises(ValueError, match="units"):
        replace(request, target_unit_id=request.source_unit_id)
    with pytest.raises(ValueError, match="versions"):
        replace(request, expected_membership_version=0)
    with pytest.raises(ValueError, match="counts"):
        replace(impact, reservations=-1)
    with pytest.raises(ValueError, match="state_digest"):
        replace(impact, state_digest="invalid")
    for key in ("", " key", "x" * 129, "bad\nkey"):
        with pytest.raises(ValueError):
            PersonnelTransferCommand(uuid4(), key, actor_id, request, "a" * 64)
