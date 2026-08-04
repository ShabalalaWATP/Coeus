"""Application port for fail-closed organisation deactivation."""

from typing import Protocol

from coeus.domain.organisation_deactivation import (
    OrganisationDeactivationCommand,
    OrganisationDeactivationImpact,
    OrganisationDeactivationRequest,
    OrganisationDeactivationResult,
)


class OrganisationDeactivationStore(Protocol):
    def inspect(
        self, request: OrganisationDeactivationRequest
    ) -> OrganisationDeactivationImpact: ...

    def replay(
        self, command: OrganisationDeactivationCommand
    ) -> OrganisationDeactivationResult | None: ...

    def apply(self, command: OrganisationDeactivationCommand) -> OrganisationDeactivationResult: ...
