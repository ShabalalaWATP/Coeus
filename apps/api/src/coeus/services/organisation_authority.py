"""Central scope policy and disabled management-grant command service."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from coeus.application.ports.organisation import OrganisationReader
from coeus.application.ports.organisation_authority import OrganisationGrantCommandStore
from coeus.domain.organisation import ManagementAction, OrganisationManagementGrant
from coeus.domain.organisation_authority import (
    CreateManagementGrantCommand,
    GrantCommandResult,
    OrganisationAuthorityConflict,
    OrganisationAuthorityDenied,
    RevokeManagementGrantCommand,
    ScopeDecision,
    command_hash,
)


class OrganisationScopeEvaluator:
    """Evaluate one action without inferring authority from hierarchy or roles."""

    def __init__(self, organisation: OrganisationReader) -> None:
        self._organisation = organisation

    def evaluate(
        self,
        principal_id: UUID,
        target_unit_id: UUID,
        action: ManagementAction,
        effective_at: datetime,
        *,
        required_grant_id: UUID | None = None,
    ) -> ScopeDecision:
        candidates = self._organisation.effective_grants(principal_id, effective_at)
        for grant in candidates:
            if required_grant_id is not None and grant.grant_id != required_grant_id:
                continue
            if grant.action is not action or not self._covers(grant, target_unit_id):
                continue
            if self._lineage_is_effective(grant, principal_id, effective_at):
                return ScopeDecision(True, grant.grant_id, "explicit_grant")
        return ScopeDecision(False, None, "no_effective_scoped_grant")

    def _lineage_is_effective(
        self,
        leaf: OrganisationManagementGrant,
        principal_id: UUID,
        effective_at: datetime,
    ) -> bool:
        current = leaf
        visited: set[UUID] = set()
        expected_manager = principal_id
        while True:
            if current.grant_id in visited or current.manager_user_id != expected_manager:
                return False
            visited.add(current.grant_id)
            if not _locally_effective(current, effective_at):
                return False
            if current.source_grant_id is None:
                return current.delegation_depth == 0
            source = self._organisation.get_management_grant(current.source_grant_id)
            if source is None or source.action is not current.action:
                return False
            if current.delegation_depth != source.delegation_depth + 1:
                return False
            if current.created_by_user_id != source.manager_user_id:
                return False
            if current.include_descendants and not source.include_descendants:
                return False
            if not self._covers(source, current.root_unit_id):
                return False
            expected_manager = source.manager_user_id
            current = source

    def _covers(self, grant: OrganisationManagementGrant, target_unit_id: UUID) -> bool:
        if grant.root_unit_id == target_unit_id:
            return True
        return grant.include_descendants and self._organisation.unit_is_within(
            grant.root_unit_id, target_unit_id
        )


class OrganisationGrantService:
    """Validate policy, then delegate atomic grant mutation to PostgreSQL."""

    def __init__(
        self,
        organisation: OrganisationReader,
        commands: OrganisationGrantCommandStore,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._organisation = organisation
        self._commands = commands
        self._scope = OrganisationScopeEvaluator(organisation)
        self._clock = clock or (lambda: datetime.now(UTC))

    def create(self, command: CreateManagementGrantCommand) -> GrantCommandResult:
        request_hash = command_hash(command)
        replay = self._commands.replay_result(
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            request_hash=request_hash,
            command_type="create",
            actor_user_id=command.actor_user_id,
            grant_id=command.grant_id,
        )
        if replay is not None:
            return replay
        occurred_at = self._clock()
        source = self._organisation.get_management_grant(command.source_grant_id)
        if source is None or source.version != command.expected_source_version:
            raise OrganisationAuthorityConflict("source grant version is no longer current")
        management = self._require(
            command.actor_user_id,
            command.root_unit_id,
            ManagementAction.GRANT_MANAGE,
            occurred_at,
        )
        self._require(
            command.actor_user_id,
            command.root_unit_id,
            command.action,
            occurred_at,
            required_grant_id=source.grant_id,
        )
        if command.include_descendants and not source.include_descendants:
            raise OrganisationAuthorityDenied("source grant cannot delegate descendant scope")
        if source.delegation_depth >= 2:
            raise OrganisationAuthorityDenied("maximum delegation depth reached")
        if source.valid_until is not None and (
            command.valid_until is None or command.valid_until > source.valid_until
        ):
            raise OrganisationAuthorityDenied("delegation cannot outlive its source grant")
        if command.valid_until is not None and command.valid_until <= occurred_at:
            raise ValueError("valid_until must be later than the transaction time")
        grant = OrganisationManagementGrant(
            grant_id=command.grant_id,
            manager_user_id=command.manager_user_id,
            root_unit_id=command.root_unit_id,
            action=command.action,
            include_descendants=command.include_descendants,
            valid_from=occurred_at,
            valid_until=command.valid_until,
            created_by_user_id=command.actor_user_id,
            reason=command.reason,
            source_grant_id=source.grant_id,
            delegation_depth=source.delegation_depth + 1,
        )
        return self._commands.create_grant(
            grant,
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            request_hash=request_hash,
            actor_user_id=command.actor_user_id,
            management_grant_id=management,
            source_expected_version=command.expected_source_version,
            occurred_at=occurred_at,
        )

    def revoke(self, command: RevokeManagementGrantCommand) -> GrantCommandResult:
        request_hash = command_hash(command)
        replay = self._commands.replay_result(
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            request_hash=request_hash,
            command_type="revoke",
            actor_user_id=command.actor_user_id,
            grant_id=command.grant_id,
        )
        if replay is not None:
            return replay
        occurred_at = self._clock()
        target = self._organisation.get_management_grant(command.grant_id)
        if target is None or target.version != command.expected_version:
            raise OrganisationAuthorityConflict("grant version is no longer current")
        management = self._require(
            command.actor_user_id,
            target.root_unit_id,
            ManagementAction.GRANT_MANAGE,
            occurred_at,
        )
        return self._commands.revoke_grant(
            command,
            request_hash=request_hash,
            management_grant_id=management,
            occurred_at=occurred_at,
        )

    def _require(
        self,
        principal_id: UUID,
        target_unit_id: UUID,
        action: ManagementAction,
        effective_at: datetime,
        *,
        required_grant_id: UUID | None = None,
    ) -> UUID:
        decision = self._scope.evaluate(
            principal_id,
            target_unit_id,
            action,
            effective_at,
            required_grant_id=required_grant_id,
        )
        if not decision.allowed or decision.evidence_grant_id is None:
            raise OrganisationAuthorityDenied("no effective scoped grant")
        return decision.evidence_grant_id


def _locally_effective(grant: OrganisationManagementGrant, effective_at: datetime) -> bool:
    return (
        grant.valid_from <= effective_at
        and (grant.valid_until is None or effective_at < grant.valid_until)
        and (grant.revoked_at is None or effective_at < grant.revoked_at)
    )
