"""Application port for transactional organisation reparenting."""

from typing import Protocol

from coeus.domain.organisation_reparent import (
    OrganisationReparentCommand,
    OrganisationReparentImpact,
    OrganisationReparentRequest,
    OrganisationReparentResult,
)


class OrganisationReparentStore(Protocol):
    def inspect(self, request: OrganisationReparentRequest) -> OrganisationReparentImpact: ...

    def replay(self, command: OrganisationReparentCommand) -> OrganisationReparentResult | None: ...

    def apply(self, command: OrganisationReparentCommand) -> OrganisationReparentResult: ...
