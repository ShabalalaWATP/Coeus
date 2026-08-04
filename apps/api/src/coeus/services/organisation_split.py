"""Policy boundary for explicit-mapping organisation splits."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from coeus.application.ports.organisation import OrganisationReader
from coeus.application.ports.organisation_split import OrganisationSplitStore
from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_split import (
    OrganisationSplitCommand,
    OrganisationSplitConflict,
    OrganisationSplitDenied,
    OrganisationSplitImpact,
    OrganisationSplitPlan,
    OrganisationSplitPreview,
    OrganisationSplitRequest,
    OrganisationSplitResult,
    split_hash,
    validate_split_dispositions,
)
from coeus.services.organisation_authority import OrganisationScopeEvaluator


class OrganisationSplitService:
    def __init__(
        self,
        organisation: OrganisationReader,
        store: OrganisationSplitStore,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._organisation = organisation
        self._store = store
        self._scope = OrganisationScopeEvaluator(organisation)
        self._clock = clock or (lambda: datetime.now(UTC))

    def assess(
        self, request: OrganisationSplitRequest, actor_user_id: UUID
    ) -> OrganisationSplitImpact:
        source = self._organisation.get_unit(request.source.unit_id)
        parent = self._organisation.get_unit(request.parent.unit_id)
        if source is None or not source.is_active or source.parent_unit_id is None:
            raise OrganisationSplitConflict("the split source is unavailable")
        if source.version != request.source.expected_version:
            raise OrganisationSplitConflict("the split source version is stale")
        if source.parent_unit_id != request.parent.unit_id:
            raise OrganisationSplitConflict("the source parent changed")
        if (
            parent is None
            or not parent.is_active
            or parent.version != request.parent.expected_version
        ):
            raise OrganisationSplitConflict("the split parent is unavailable or stale")
        self._require_authority(request, actor_user_id)
        impact = self._store.inspect(request)
        if impact.reservations or impact.team_calendar_events or impact.saved_views:
            raise OrganisationSplitConflict("unsupported dependent records require disposition")
        return impact

    def preview(self, plan: OrganisationSplitPlan, actor_user_id: UUID) -> OrganisationSplitPreview:
        impact = self.assess(plan.request, actor_user_id)
        validate_split_dispositions(plan, impact)
        return OrganisationSplitPreview(plan, impact, split_hash(plan, actor_user_id, impact))

    def execute(self, command: OrganisationSplitCommand) -> OrganisationSplitResult:
        replay = self._store.replay(command)
        if replay is not None:
            return replay
        preview = self.preview(command.plan, command.actor_user_id)
        if preview.preview_hash != command.preview_hash:
            raise OrganisationSplitConflict("the split preview is stale")
        return self._store.apply(command)

    def _require_authority(self, request: OrganisationSplitRequest, actor_user_id: UUID) -> None:
        occurred_at = self._clock()
        for unit_id, grant_id in (
            (request.source.unit_id, request.source_authorising_grant_id),
            (request.parent.unit_id, request.parent_authorising_grant_id),
        ):
            decision = self._scope.evaluate(
                actor_user_id,
                unit_id,
                ManagementAction.ORGANISATION_RESTRUCTURE,
                occurred_at,
                required_grant_id=grant_id,
            )
            if not decision.allowed:
                raise OrganisationSplitDenied("no effective restructure grant for split scope")
