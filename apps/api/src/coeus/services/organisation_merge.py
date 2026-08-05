"""Policy and disposition validation for organisation unit merges."""

from collections.abc import Callable
from datetime import UTC, datetime
from itertools import combinations
from uuid import UUID

from coeus.application.ports.organisation import OrganisationReader
from coeus.application.ports.organisation_merge import OrganisationMergeStore
from coeus.domain.organisation import MAX_ORGANISATION_DEPTH, ManagementAction
from coeus.domain.organisation_merge import (
    MergeUnitVersion,
    OrganisationMergeCommand,
    OrganisationMergeConflict,
    OrganisationMergeDenied,
    OrganisationMergeImpact,
    OrganisationMergePlan,
    OrganisationMergePreview,
    OrganisationMergeRequest,
    OrganisationMergeResult,
    merge_hash,
    validate_merge_dispositions,
)
from coeus.services.organisation_authority import OrganisationScopeEvaluator


class OrganisationMergeService:
    def __init__(
        self,
        organisation: OrganisationReader,
        store: OrganisationMergeStore,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._organisation = organisation
        self._store = store
        self._scope = OrganisationScopeEvaluator(organisation)
        self._clock = clock or (lambda: datetime.now(UTC))

    def assess(
        self, request: OrganisationMergeRequest, actor_user_id: UUID
    ) -> OrganisationMergeImpact:
        units = (*request.sources, request.successor)
        self._validate_units(request, units)
        self._validate_relationships(request)
        self._validate_authority(request, units, actor_user_id)
        impact = self._store.inspect(request)
        _validate_impact(impact)
        return impact

    def _validate_units(
        self,
        request: OrganisationMergeRequest,
        units: tuple[MergeUnitVersion, ...],
    ) -> None:
        for expected in units:
            unit = self._organisation.get_unit(expected.unit_id)
            if unit is None or not unit.is_active:
                raise OrganisationMergeConflict("an affected organisation unit is not active")
            if unit.version != expected.expected_version:
                raise OrganisationMergeConflict("an affected organisation unit version is stale")
            if expected in request.sources and unit.parent_unit_id is None:
                raise OrganisationMergeConflict("a root organisation unit cannot be merged")

    def _validate_relationships(self, request: OrganisationMergeRequest) -> None:
        if any(
            self._organisation.unit_is_within(source.unit_id, request.successor.unit_id)
            for source in request.sources
        ):
            raise OrganisationMergeConflict("the successor cannot be inside a source subtree")
        if any(
            self._organisation.unit_is_within(left.unit_id, right.unit_id)
            or self._organisation.unit_is_within(right.unit_id, left.unit_id)
            for left, right in combinations(request.sources, 2)
        ):
            raise OrganisationMergeConflict("merge source subtrees cannot overlap")

    def _validate_authority(
        self,
        request: OrganisationMergeRequest,
        units: tuple[MergeUnitVersion, ...],
        actor_user_id: UUID,
    ) -> None:
        grant_by_unit = {item.unit_id: item.grant_id for item in request.authorities}
        occurred_at = self._clock()
        for expected in units:
            decision = self._scope.evaluate(
                actor_user_id,
                expected.unit_id,
                ManagementAction.ORGANISATION_RESTRUCTURE,
                occurred_at,
                required_grant_id=grant_by_unit[expected.unit_id],
            )
            if not decision.allowed:
                raise OrganisationMergeDenied("no effective restructure grant for every unit")

    def preview(self, plan: OrganisationMergePlan, actor_user_id: UUID) -> OrganisationMergePreview:
        impact = self.assess(plan.request, actor_user_id)
        validate_merge_dispositions(plan, impact)
        return OrganisationMergePreview(plan, impact, merge_hash(plan, actor_user_id, impact))

    def execute(self, command: OrganisationMergeCommand) -> OrganisationMergeResult:
        replay = self._store.replay(command)
        if replay is not None:
            return replay
        preview = self.preview(command.plan, command.actor_user_id)
        if preview.preview_hash != command.preview_hash:
            raise OrganisationMergeConflict("the merge preview is stale")
        return self._store.apply(command)


def _validate_impact(impact: OrganisationMergeImpact) -> None:
    if impact.maximum_result_depth > MAX_ORGANISATION_DEPTH:
        raise OrganisationMergeConflict("the merged hierarchy would exceed maximum depth")
    if impact.newly_covering_grants:
        raise OrganisationMergeConflict(
            "the merge would silently broaden one or more management grants"
        )
    if impact.reservations or impact.team_calendar_events or impact.saved_views:
        raise OrganisationMergeConflict("unsupported dependent records require disposition")
