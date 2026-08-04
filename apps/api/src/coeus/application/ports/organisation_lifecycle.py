"""Transactional port for previewed organisation unit lifecycle commands."""

from typing import Protocol

from coeus.domain.organisation_lifecycle import (
    OrganisationMutationCommand,
    OrganisationMutationResult,
)


class OrganisationMutationStore(Protocol):
    def replay(self, command: OrganisationMutationCommand) -> OrganisationMutationResult | None: ...

    def apply(self, command: OrganisationMutationCommand) -> OrganisationMutationResult: ...
