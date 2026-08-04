"""Application port for explicit-disposition organisation merges."""

from typing import Protocol

from coeus.domain.organisation_merge import (
    OrganisationMergeCommand,
    OrganisationMergeImpact,
    OrganisationMergeRequest,
    OrganisationMergeResult,
)


class OrganisationMergeStore(Protocol):
    def inspect(self, request: OrganisationMergeRequest) -> OrganisationMergeImpact: ...

    def replay(self, command: OrganisationMergeCommand) -> OrganisationMergeResult | None: ...

    def apply(self, command: OrganisationMergeCommand) -> OrganisationMergeResult: ...
