"""Authorisation and preview policy for organisation reparent commands."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from coeus.application.ports.organisation import OrganisationReader
from coeus.application.ports.organisation_reparent import OrganisationReparentStore
from coeus.domain.organisation import MAX_ORGANISATION_DEPTH, ManagementAction, OrganisationUnit
from coeus.domain.organisation_reparent import (
    OrganisationReparentCommand,
    OrganisationReparentConflict,
    OrganisationReparentDenied,
    OrganisationReparentPreview,
    OrganisationReparentRequest,
    OrganisationReparentResult,
    reparent_hash,
)
from coeus.services.organisation_authority import OrganisationScopeEvaluator


class OrganisationReparentService:
    def __init__(
        self,
        organisation: OrganisationReader,
        store: OrganisationReparentStore,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._organisation = organisation
        self._store = store
        self._scope = OrganisationScopeEvaluator(organisation)
        self._clock = clock or (lambda: datetime.now(UTC))

    def preview(
        self, request: OrganisationReparentRequest, actor_user_id: UUID
    ) -> OrganisationReparentPreview:
        source, target = self._validate_units(request)
        self._require_authority(request, actor_user_id, source.unit_id, target.unit_id)
        impact = self._store.inspect(request)
        if impact.source_parent_unit_id != source.parent_unit_id:
            raise OrganisationReparentConflict("the source topology changed during preview")
        if impact.maximum_result_depth > MAX_ORGANISATION_DEPTH:
            raise OrganisationReparentConflict("the organisation depth limit would be exceeded")
        if impact.newly_covering_grants:
            raise OrganisationReparentConflict(
                "reparenting would silently broaden one or more management grants"
            )
        return OrganisationReparentPreview(
            source.unit_id,
            target.unit_id,
            impact,
            reparent_hash(request, actor_user_id, impact),
        )

    def _validate_units(
        self, request: OrganisationReparentRequest
    ) -> tuple[OrganisationUnit, OrganisationUnit]:
        source = self._organisation.get_unit(request.unit_id)
        target = self._organisation.get_unit(request.new_parent_unit_id)
        if source is None or not source.is_active:
            raise OrganisationReparentConflict("the organisation unit is not active")
        if source.parent_unit_id is None:
            raise OrganisationReparentConflict("the root organisation unit cannot be reparented")
        if source.version != request.expected_unit_version:
            raise OrganisationReparentConflict("the organisation unit version is stale")
        if target is None or not target.is_active:
            raise OrganisationReparentConflict("the new parent unit is not active")
        if target.version != request.expected_parent_version:
            raise OrganisationReparentConflict("the new parent unit version is stale")
        if source.parent_unit_id == target.unit_id:
            raise OrganisationReparentConflict("the unit already has this parent")
        if self._organisation.unit_is_within(source.unit_id, target.unit_id):
            raise OrganisationReparentConflict("the new parent would create a cycle")
        return source, target

    def execute(self, command: OrganisationReparentCommand) -> OrganisationReparentResult:
        replay = self._store.replay(command)
        if replay is not None:
            return replay
        preview = self.preview(command.request, command.actor_user_id)
        if preview.preview_hash != command.preview_hash:
            raise OrganisationReparentConflict("the reparent preview is stale")
        return self._store.apply(command)

    def _require_authority(
        self,
        request: OrganisationReparentRequest,
        actor_user_id: UUID,
        source_unit_id: UUID,
        target_unit_id: UUID,
    ) -> None:
        at = self._clock()
        for unit_id in (source_unit_id, target_unit_id):
            decision = self._scope.evaluate(
                actor_user_id,
                unit_id,
                ManagementAction.ORGANISATION_REPARENT,
                at,
                required_grant_id=request.authorising_grant_id,
            )
            if not decision.allowed:
                raise OrganisationReparentDenied(
                    "one effective grant must cover both the source and new parent"
                )
