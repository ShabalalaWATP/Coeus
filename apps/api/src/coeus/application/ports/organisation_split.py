"""Application port for explicit-mapping organisation splits."""

from typing import Protocol

from coeus.domain.organisation_split import (
    OrganisationSplitCommand,
    OrganisationSplitImpact,
    OrganisationSplitRequest,
    OrganisationSplitResult,
)


class OrganisationSplitStore(Protocol):
    def inspect(self, request: OrganisationSplitRequest) -> OrganisationSplitImpact: ...

    def replay(self, command: OrganisationSplitCommand) -> OrganisationSplitResult | None: ...

    def apply(self, command: OrganisationSplitCommand) -> OrganisationSplitResult: ...
