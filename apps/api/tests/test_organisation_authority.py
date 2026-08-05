"""Policy and command tests for the disabled organisation authority slice."""

import importlib
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from coeus.domain.organisation import ManagementAction, OrganisationManagementGrant
from coeus.domain.organisation_authority import (
    CreateManagementGrantCommand,
    GrantCommandResult,
    OrganisationAuthorityConflict,
    OrganisationAuthorityDenied,
    RevokeManagementGrantCommand,
)
from coeus.persistence.organisation_authority_schema import (
    organisation_authority_schema_statements,
)
from coeus.services.organisation_authority import (
    OrganisationGrantService,
    OrganisationScopeEvaluator,
)

NOW = datetime(2026, 8, 3, 12, tzinfo=UTC)


class _Organisation:
    def __init__(
        self, grants: tuple[OrganisationManagementGrant, ...], paths: set[tuple[UUID, UUID]]
    ):
        self.grants = {grant.grant_id: grant for grant in grants}
        self.paths = paths

    def effective_grants(self, manager_user_id: UUID, effective_at: datetime):  # type: ignore[no-untyped-def]
        return tuple(
            grant
            for grant in self.grants.values()
            if grant.manager_user_id == manager_user_id
            and grant.valid_from <= effective_at
            and (grant.valid_until is None or effective_at < grant.valid_until)
            and (grant.revoked_at is None or effective_at < grant.revoked_at)
        )

    def get_management_grant(self, grant_id: UUID):  # type: ignore[no-untyped-def]
        return self.grants.get(grant_id)

    def unit_is_within(self, root_unit_id: UUID, target_unit_id: UUID) -> bool:
        return root_unit_id == target_unit_id or (root_unit_id, target_unit_id) in self.paths


class _Commands:
    def __init__(self) -> None:
        self.created: OrganisationManagementGrant | None = None
        self.replay: GrantCommandResult | None = None

    def replay_result(self, **kwargs: object) -> GrantCommandResult | None:
        return self.replay

    def create_grant(
        self, grant: OrganisationManagementGrant, **kwargs: object
    ) -> GrantCommandResult:
        self.created = grant
        return GrantCommandResult(grant.grant_id, 1)

    def revoke_grant(
        self, command: RevokeManagementGrantCommand, **kwargs: object
    ) -> GrantCommandResult:
        return GrantCommandResult(command.grant_id, command.expected_version + 1)


def _grant(
    manager: UUID,
    root: UUID,
    action: ManagementAction,
    *,
    descendants: bool = True,
    source: OrganisationManagementGrant | None = None,
) -> OrganisationManagementGrant:
    return OrganisationManagementGrant(
        uuid4(),
        manager,
        root,
        action,
        descendants,
        NOW,
        source.manager_user_id if source else manager,
        "Synthetic authority fixture",
        source_grant_id=None if source is None else source.grant_id,
        delegation_depth=0 if source is None else source.delegation_depth + 1,
    )


def test_scope_is_action_specific_direct_or_descendant_and_never_parent_inherited() -> None:
    manager, root, child, sibling = uuid4(), uuid4(), uuid4(), uuid4()
    direct = _grant(manager, root, ManagementAction.ROSTER_VIEW, descendants=False)
    descendant = _grant(manager, root, ManagementAction.TASK_VIEW)
    evaluator = OrganisationScopeEvaluator(_Organisation((direct, descendant), {(root, child)}))  # type: ignore[arg-type]
    assert evaluator.evaluate(manager, root, ManagementAction.ROSTER_VIEW, NOW).allowed
    assert not evaluator.evaluate(manager, child, ManagementAction.ROSTER_VIEW, NOW).allowed
    assert evaluator.evaluate(manager, child, ManagementAction.TASK_VIEW, NOW).allowed
    assert not evaluator.evaluate(manager, sibling, ManagementAction.TASK_VIEW, NOW).allowed
    assert not evaluator.evaluate(manager, child, ManagementAction.TASK_ASSIGN, NOW).allowed


def test_revoked_or_invalid_source_immediately_invalidates_delegated_grant() -> None:
    root_manager, child_manager, root, child = uuid4(), uuid4(), uuid4(), uuid4()
    source = _grant(root_manager, root, ManagementAction.TASK_VIEW)
    delegated = _grant(child_manager, child, ManagementAction.TASK_VIEW, source=source)
    organisation = _Organisation((source, delegated), {(root, child)})
    evaluator = OrganisationScopeEvaluator(organisation)  # type: ignore[arg-type]
    assert evaluator.evaluate(child_manager, child, ManagementAction.TASK_VIEW, NOW).allowed
    organisation.grants[source.grant_id] = replace(
        source,
        revoked_at=NOW,
        revoked_by_user_id=root_manager,
        revocation_reason="Synthetic revocation",
        version=2,
    )
    assert not evaluator.evaluate(child_manager, child, ManagementAction.TASK_VIEW, NOW).allowed


@pytest.mark.parametrize(
    "mutate",
    (
        lambda grant, source: replace(grant, source_grant_id=uuid4()),
        lambda grant, source: replace(grant, delegation_depth=source.delegation_depth + 2),
        lambda grant, source: replace(grant, created_by_user_id=uuid4()),
        lambda grant, source: replace(grant, root_unit_id=uuid4()),
    ),
)
def test_malformed_delegation_lineage_never_grants_authority(
    mutate: Callable[
        [OrganisationManagementGrant, OrganisationManagementGrant], OrganisationManagementGrant
    ],
) -> None:
    root_manager, child_manager, root, child = uuid4(), uuid4(), uuid4(), uuid4()
    source = _grant(root_manager, root, ManagementAction.TASK_VIEW)
    delegated = _grant(child_manager, child, ManagementAction.TASK_VIEW, source=source)
    malformed = mutate(delegated, source)
    organisation = _Organisation((source, malformed), {(root, child)})
    evaluator = OrganisationScopeEvaluator(organisation)  # type: ignore[arg-type]
    assert not evaluator.evaluate(
        malformed.manager_user_id, malformed.root_unit_id, ManagementAction.TASK_VIEW, NOW
    ).allowed


def test_create_requires_manage_and_matching_action_ceiling() -> None:
    actor, recipient, root, child = uuid4(), uuid4(), uuid4(), uuid4()
    manage = _grant(actor, root, ManagementAction.GRANT_MANAGE)
    ceiling = _grant(actor, root, ManagementAction.TASK_ASSIGN)
    organisation = _Organisation((manage, ceiling), {(root, child)})
    commands = _Commands()
    service = OrganisationGrantService(organisation, commands, clock=lambda: NOW)  # type: ignore[arg-type]
    command = CreateManagementGrantCommand(
        uuid4(),
        uuid4(),
        "create-1",
        actor,
        recipient,
        child,
        ManagementAction.TASK_ASSIGN,
        False,
        ceiling.grant_id,
        1,
        "Synthetic delegated assignment authority",
        NOW + timedelta(days=7),
    )
    result = service.create(command)
    assert result.version == 1
    assert commands.created is not None
    assert commands.created.source_grant_id == ceiling.grant_id
    assert commands.created.valid_from == NOW

    denied = replace(
        command,
        command_id=uuid4(),
        grant_id=uuid4(),
        idempotency_key="create-2",
        action=ManagementAction.TASK_APPROVE,
    )
    with pytest.raises(OrganisationAuthorityDenied):
        service.create(denied)


def test_revoke_uses_expected_version_and_replay_precedes_stale_reads() -> None:
    actor, root = uuid4(), uuid4()
    manage = _grant(actor, root, ManagementAction.GRANT_MANAGE)
    target = _grant(uuid4(), root, ManagementAction.TASK_VIEW)
    organisation = _Organisation((manage, target), set())
    commands = _Commands()
    service = OrganisationGrantService(organisation, commands, clock=lambda: NOW)  # type: ignore[arg-type]
    command = RevokeManagementGrantCommand(
        uuid4(), "revoke-1", actor, target.grant_id, 1, "Expired need"
    )
    assert service.revoke(command).version == 2
    commands.replay = GrantCommandResult(target.grant_id, 2, True)
    organisation.grants[target.grant_id] = replace(target, version=2)
    assert service.revoke(command).replayed


@pytest.mark.parametrize(
    ("change", "message"),
    (
        ({"expected_source_version": 0}, "expected_source_version"),
        ({"valid_until": datetime(2026, 8, 4)}, "timezone-aware"),
        ({"idempotency_key": ""}, "idempotency_key"),
        ({"idempotency_key": "bad\nkey"}, "control characters"),
        ({"reason": ""}, "reason"),
        ({"reason": "bad\nreason"}, "control characters"),
    ),
)
def test_create_command_rejects_invalid_boundaries(change: dict[str, object], message: str) -> None:
    command = CreateManagementGrantCommand(
        uuid4(),
        uuid4(),
        "valid-key",
        uuid4(),
        uuid4(),
        uuid4(),
        ManagementAction.TASK_VIEW,
        False,
        uuid4(),
        1,
        "Synthetic reason",
    )
    with pytest.raises(ValueError, match=message):
        replace(command, **change)


def test_revoke_command_rejects_invalid_version() -> None:
    with pytest.raises(ValueError, match="expected_version"):
        RevokeManagementGrantCommand(uuid4(), "revoke", uuid4(), uuid4(), 0, "Reason")


def test_create_and_revoke_cover_policy_conflicts() -> None:
    actor, recipient, root = uuid4(), uuid4(), uuid4()
    manage = _grant(actor, root, ManagementAction.GRANT_MANAGE)
    ceiling = _grant(actor, root, ManagementAction.TASK_VIEW)
    organisation = _Organisation((manage, ceiling), set())
    commands = _Commands()
    service = OrganisationGrantService(organisation, commands, clock=lambda: NOW)  # type: ignore[arg-type]
    base = CreateManagementGrantCommand(
        uuid4(),
        uuid4(),
        "edge-create",
        actor,
        recipient,
        root,
        ManagementAction.TASK_VIEW,
        False,
        ceiling.grant_id,
        1,
        "Synthetic delegated view",
        NOW + timedelta(days=2),
    )

    commands.replay = GrantCommandResult(base.grant_id, 1, True)
    assert service.create(base).replayed
    commands.replay = None
    with pytest.raises(OrganisationAuthorityConflict, match="source grant version"):
        service.create(replace(base, expected_source_version=2))

    direct_only = replace(ceiling, include_descendants=False)
    organisation.grants[ceiling.grant_id] = direct_only
    with pytest.raises(OrganisationAuthorityDenied, match="descendant scope"):
        service.create(replace(base, include_descendants=True))

    organisation.grants[ceiling.grant_id] = ceiling
    level_one = _grant(actor, root, ManagementAction.TASK_VIEW, source=ceiling)
    depth_two = _grant(actor, root, ManagementAction.TASK_VIEW, source=level_one)
    organisation.grants[level_one.grant_id] = level_one
    organisation.grants[depth_two.grant_id] = depth_two
    with pytest.raises(OrganisationAuthorityDenied, match="maximum delegation"):
        service.create(replace(base, source_grant_id=depth_two.grant_id))

    expiring = replace(ceiling, valid_until=NOW + timedelta(days=1))
    organisation.grants[ceiling.grant_id] = expiring
    with pytest.raises(OrganisationAuthorityDenied, match="outlive"):
        service.create(base)

    organisation.grants[ceiling.grant_id] = ceiling
    with pytest.raises(ValueError, match="later than the transaction"):
        service.create(replace(base, valid_until=NOW))

    target = _grant(recipient, root, ManagementAction.TASK_ASSIGN)
    organisation.grants[target.grant_id] = target
    revoke = RevokeManagementGrantCommand(
        uuid4(), "stale-revoke", actor, target.grant_id, 2, "No longer required"
    )
    with pytest.raises(OrganisationAuthorityConflict, match="grant version"):
        service.revoke(revoke)


def test_0018_migration_uses_the_exact_runtime_authority_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module(
        "coeus.db.migrations.versions.20260803_0018_organisation_grant_authority"
    )
    executed: list[str] = []
    monkeypatch.setattr(module.op, "execute", executed.append)
    module.upgrade()
    assert module.revision == "20260803_0018"
    assert module.down_revision == "20260803_0017"
    assert tuple(executed[2:]) == tuple(organisation_authority_schema_statements())
    assert all("provenance" in statement for statement in executed[:2])
    ddl = "\n".join(executed)
    assert "organisation_grant_commands" in ddl
    assert "trg_organisation_grant_lineage_immutable" in ddl
    assert "revoked_by_user_id" in ddl
