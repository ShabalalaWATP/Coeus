"""Policy boundary for scheduled and immediate single-home transfers."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from coeus.application.ports.access import UserLookup
from coeus.application.ports.organisation import OrganisationReader
from coeus.application.ports.organisation_transfer import OrganisationTransferStore
from coeus.domain.organisation import (
    ManagementAction,
    MembershipState,
    OrganisationCategory,
    TeamMembership,
)
from coeus.domain.organisation_transfer import (
    PersonnelTransferCommand,
    PersonnelTransferConflict,
    PersonnelTransferDenied,
    PersonnelTransferPreview,
    PersonnelTransferRequest,
    PersonnelTransferResult,
    personnel_transfer_hash,
)
from coeus.services.organisation_authority import OrganisationScopeEvaluator
from coeus.services.workforce_authority import (
    PROCESS_WORKFORCE_AUTHORITY,
    WorkforceAuthority,
)


class OrganisationTransferService:
    def __init__(
        self,
        organisation: OrganisationReader,
        users: UserLookup,
        store: OrganisationTransferStore,
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
        self, request: PersonnelTransferRequest, actor_user_id: UUID
    ) -> PersonnelTransferPreview:
        now = self._clock()
        self._active_user(request.user_id)
        source = self._source_membership(request)
        target = self._organisation.get_unit(request.target_unit_id)
        if target is None or not target.is_active:
            raise PersonnelTransferConflict("the target organisation unit is not active")
        if target.version != request.expected_target_unit_version:
            raise PersonnelTransferConflict("the target organisation unit version is stale")
        if (
            request.assignment_eligible
            and target.category is not OrganisationCategory.DELIVERY_TEAM
        ):
            raise PersonnelTransferConflict(
                "assignment eligibility requires a delivery team membership"
            )
        if request.effective_at < now or request.effective_at <= source.valid_from:
            raise PersonnelTransferConflict("the transfer boundary must be in the future")
        self._require_grants(request, actor_user_id, now)
        self._require_grants(request, actor_user_id, request.effective_at)
        impact = self._store.inspect(request)
        return PersonnelTransferPreview(
            request,
            impact,
            personnel_transfer_hash(request, actor_user_id, impact),
        )

    def execute(self, command: PersonnelTransferCommand) -> PersonnelTransferResult:
        replay = self._store.replay(command)
        if replay is not None:
            return replay
        with self._workforce_authority.locked():
            preview = self.preview(command.request, command.actor_user_id)
            if preview.preview_hash != command.preview_hash:
                raise PersonnelTransferConflict("the personnel transfer preview is stale")
            return self._store.apply(command)

    def activate_due(self, *, limit: int = 100) -> tuple[PersonnelTransferResult, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between one and 100")
        results: list[PersonnelTransferResult] = []
        for command in self._store.due(self._clock(), limit=limit):
            with self._workforce_authority.locked():
                user = self._users.get_user(command.request.user_id)
                if user is None or not user.is_active:
                    results.append(self._store.block(command, "account_inactive"))
                    continue
                try:
                    results.append(self._store.activate(command))
                except PersonnelTransferDenied:
                    results.append(self._store.block(command, "authority_lost"))
                except PersonnelTransferConflict:
                    results.append(self._store.block(command, "state_changed"))
        return tuple(results)

    def _active_user(self, user_id: UUID) -> None:
        user = self._users.get_user(user_id)
        if user is None or not user.is_active:
            raise PersonnelTransferConflict("the user account is not active")

    def _source_membership(self, request: PersonnelTransferRequest) -> TeamMembership:
        source = next(
            (
                item
                for item in self._organisation.list_memberships(request.user_id)
                if item.membership_id == request.source_membership_id
            ),
            None,
        )
        valid = (
            source is not None
            and source.user_id == request.user_id
            and source.unit_id == request.source_unit_id
            and source.state is MembershipState.ACTIVE
            and source.valid_until is None
            and source.version == request.expected_membership_version
        )
        if not valid or source is None:
            raise PersonnelTransferConflict("the source membership is not current")
        return source

    def _require_grants(
        self, request: PersonnelTransferRequest, actor_user_id: UUID, at: datetime
    ) -> None:
        checks = (
            (request.source_unit_id, request.source_authorising_grant_id),
            (request.target_unit_id, request.target_authorising_grant_id),
        )
        for unit_id, grant_id in checks:
            decision = self._scope.evaluate(
                actor_user_id,
                unit_id,
                ManagementAction.ROSTER_TRANSFER,
                at,
                required_grant_id=grant_id,
            )
            if not decision.allowed:
                raise PersonnelTransferDenied(
                    "effective roster transfer grants must cover both endpoints"
                )
