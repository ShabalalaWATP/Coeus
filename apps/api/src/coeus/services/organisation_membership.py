"""Policy boundary for single-home organisation membership commands."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from coeus.application.ports.access import UserLookup
from coeus.application.ports.organisation import OrganisationReader
from coeus.application.ports.organisation_membership import OrganisationMembershipStore
from coeus.domain.organisation import ManagementAction, OrganisationCategory
from coeus.domain.organisation_membership import (
    MembershipCommandConflict,
    MembershipCommandDenied,
    MembershipMutationCommand,
    MembershipMutationPreview,
    MembershipMutationRequest,
    MembershipMutationResult,
    MembershipOperation,
    membership_hash,
)
from coeus.services.organisation_authority import OrganisationScopeEvaluator
from coeus.services.workforce_authority import (
    PROCESS_WORKFORCE_AUTHORITY,
    WorkforceAuthority,
)


class OrganisationMembershipService:
    def __init__(
        self,
        organisation: OrganisationReader,
        users: UserLookup,
        store: OrganisationMembershipStore,
        *,
        clock: Callable[[], datetime] | None = None,
        workforce_authority: WorkforceAuthority = PROCESS_WORKFORCE_AUTHORITY,
    ) -> None:
        self._organisation = organisation
        self._users = users
        self._store = store
        self._scope = OrganisationScopeEvaluator(organisation)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._workforce_authority = workforce_authority

    def preview(
        self, request: MembershipMutationRequest, actor_user_id: UUID
    ) -> MembershipMutationPreview:
        now = self._clock()
        user = self._users.get_user(request.user_id)
        if user is None or not user.is_active:
            raise MembershipCommandConflict("the user account is not active")
        unit = self._organisation.get_unit(request.unit_id)
        if unit is None or not unit.is_active:
            raise MembershipCommandConflict("the organisation unit is not active")
        if request.assignment_eligible and unit.category is not OrganisationCategory.DELIVERY_TEAM:
            raise MembershipCommandConflict(
                "assignment eligibility requires a delivery team membership"
            )
        if (
            request.operation is MembershipOperation.END
            and request.valid_until is not None
            and request.valid_until > now
        ):
            raise MembershipCommandConflict("future membership endings require a transfer command")
        decision = self._scope.evaluate(
            actor_user_id,
            request.unit_id,
            ManagementAction.ROSTER_MANAGE,
            now,
            required_grant_id=request.authorising_grant_id,
        )
        if not decision.allowed:
            raise MembershipCommandDenied("no effective roster management grant")
        snapshot = self._store.inspect(request)
        if snapshot.unit_version != unit.version:
            raise MembershipCommandConflict("the organisation unit version is stale")
        expected_membership = (
            0 if request.operation is MembershipOperation.CREATE else request.expected_version
        )
        if snapshot.current_membership_version != expected_membership:
            raise MembershipCommandConflict("the membership version is stale")
        return MembershipMutationPreview(
            request,
            snapshot,
            membership_hash(request, actor_user_id, snapshot),
        )

    def execute(self, command: MembershipMutationCommand) -> MembershipMutationResult:
        replay = self._store.replay(command)
        if replay is not None:
            return replay
        with self._workforce_authority.locked():
            preview = self.preview(command.request, command.actor_user_id)
            if preview.preview_hash != command.preview_hash:
                raise MembershipCommandConflict("the membership preview is stale")
            return self._store.apply(command)
