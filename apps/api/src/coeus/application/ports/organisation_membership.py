"""Application port for transactional organisation membership commands."""

from typing import Protocol

from coeus.domain.organisation_membership import (
    MembershipMutationCommand,
    MembershipMutationRequest,
    MembershipMutationResult,
    MembershipMutationSnapshot,
)


class OrganisationMembershipStore(Protocol):
    def inspect(self, request: MembershipMutationRequest) -> MembershipMutationSnapshot: ...

    def replay(self, command: MembershipMutationCommand) -> MembershipMutationResult | None: ...

    def apply(self, command: MembershipMutationCommand) -> MembershipMutationResult: ...
