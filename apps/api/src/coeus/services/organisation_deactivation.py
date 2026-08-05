"""Authorisation policy for fail-closed organisation deactivation."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from coeus.application.ports.organisation import OrganisationReader
from coeus.application.ports.organisation_deactivation import OrganisationDeactivationStore
from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_deactivation import (
    OrganisationDeactivationCommand,
    OrganisationDeactivationConflict,
    OrganisationDeactivationDenied,
    OrganisationDeactivationPreview,
    OrganisationDeactivationRequest,
    OrganisationDeactivationResult,
    deactivation_hash,
)
from coeus.services.organisation_authority import OrganisationScopeEvaluator


class OrganisationDeactivationService:
    def __init__(
        self,
        organisation: OrganisationReader,
        store: OrganisationDeactivationStore,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._organisation = organisation
        self._store = store
        self._scope = OrganisationScopeEvaluator(organisation)
        self._clock = clock or (lambda: datetime.now(UTC))

    def preview(
        self, request: OrganisationDeactivationRequest, actor_user_id: UUID
    ) -> OrganisationDeactivationPreview:
        unit = self._organisation.get_unit(request.unit_id)
        if unit is None or not unit.is_active:
            raise OrganisationDeactivationConflict("the organisation unit is not active")
        if unit.parent_unit_id is None:
            raise OrganisationDeactivationConflict(
                "the root organisation unit cannot be deactivated"
            )
        if unit.version != request.expected_version:
            raise OrganisationDeactivationConflict("the organisation unit version is stale")
        decision = self._scope.evaluate(
            actor_user_id,
            request.unit_id,
            ManagementAction.ORGANISATION_RESTRUCTURE,
            self._clock(),
            required_grant_id=request.authorising_grant_id,
        )
        if not decision.allowed:
            raise OrganisationDeactivationDenied("no effective organisation restructure grant")
        impact = self._store.inspect(request)
        if impact.blocking_count:
            raise OrganisationDeactivationConflict(
                "the organisation unit still has dependent records requiring disposition"
            )
        return OrganisationDeactivationPreview(
            request,
            impact,
            deactivation_hash(request, actor_user_id, impact),
        )

    def execute(self, command: OrganisationDeactivationCommand) -> OrganisationDeactivationResult:
        replay = self._store.replay(command)
        if replay is not None:
            return replay
        preview = self.preview(command.request, command.actor_user_id)
        if preview.preview_hash != command.preview_hash:
            raise OrganisationDeactivationConflict("the deactivation preview is stale")
        return self._store.apply(command)
