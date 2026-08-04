"""Authorised preview and execution policy for create/edit unit commands."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from coeus.application.ports.organisation import OrganisationReader
from coeus.application.ports.organisation_lifecycle import OrganisationMutationStore
from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_lifecycle import (
    OrganisationMutationCommand,
    OrganisationMutationConflict,
    OrganisationMutationDenied,
    OrganisationMutationOperation,
    OrganisationMutationPreview,
    OrganisationMutationRequest,
    OrganisationMutationResult,
    mutation_hash,
)
from coeus.services.organisation_authority import OrganisationScopeEvaluator


class OrganisationLifecycleService:
    def __init__(
        self,
        organisation: OrganisationReader,
        store: OrganisationMutationStore,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._organisation = organisation
        self._store = store
        self._scope = OrganisationScopeEvaluator(organisation)
        self._clock = clock or (lambda: datetime.now(UTC))

    def preview(
        self, request: OrganisationMutationRequest, actor_user_id: UUID
    ) -> OrganisationMutationPreview:
        scope_unit_id, action = self._validate_current(request)
        decision = self._scope.evaluate(
            actor_user_id,
            scope_unit_id,
            action,
            self._clock(),
            required_grant_id=request.authorising_grant_id,
        )
        if not decision.allowed:
            raise OrganisationMutationDenied("no effective scoped grant")
        return OrganisationMutationPreview(
            request.operation,
            request.unit_id,
            scope_unit_id,
            request.expected_version,
            mutation_hash(request, actor_user_id),
        )

    def execute(self, command: OrganisationMutationCommand) -> OrganisationMutationResult:
        expected_hash = mutation_hash(command.request, command.actor_user_id)
        if command.preview_hash != expected_hash:
            raise OrganisationMutationConflict("the mutation preview does not match the command")
        replay = self._store.replay(command)
        if replay is not None:
            return replay
        self.preview(command.request, command.actor_user_id)
        return self._store.apply(command)

    def _validate_current(
        self, request: OrganisationMutationRequest
    ) -> tuple[UUID, ManagementAction]:
        if request.operation is OrganisationMutationOperation.CREATE:
            parent_id = request.parent_unit_id
            assert parent_id is not None
            parent = self._organisation.get_unit(parent_id)
            if parent is None or not parent.is_active:
                raise OrganisationMutationConflict("the parent unit is not active")
            if parent.version != request.expected_version:
                raise OrganisationMutationConflict("the parent unit version is stale")
            if self._organisation.get_unit(request.unit_id) is not None:
                raise OrganisationMutationConflict("the new unit identity is already in use")
            return parent_id, ManagementAction.ORGANISATION_CREATE
        unit = self._organisation.get_unit(request.unit_id)
        if unit is None or not unit.is_active:
            raise OrganisationMutationConflict("the organisation unit is not active")
        if unit.version != request.expected_version:
            raise OrganisationMutationConflict("the organisation unit version is stale")
        if unit.category is not request.category:
            raise OrganisationMutationConflict("unit category requires a restructure command")
        unchanged = (
            unit.name == request.name
            and unit.short_name == request.short_name
            and unit.category is request.category
            and unit.time_zone == request.time_zone
            and unit.description == request.description
        )
        if unchanged:
            raise OrganisationMutationConflict("the edit does not change organisation metadata")
        return unit.unit_id, ManagementAction.ORGANISATION_EDIT
