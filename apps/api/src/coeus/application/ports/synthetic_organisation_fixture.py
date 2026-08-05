"""Port for previewing and atomically applying the synthetic organisation fixture."""

from typing import Protocol
from uuid import UUID

from coeus.domain.synthetic_organisation_fixture import (
    SyntheticFixtureCommand,
    SyntheticFixturePreview,
    SyntheticFixtureResult,
    SyntheticFixtureUser,
)


class SyntheticOrganisationFixtureStore(Protocol):
    def preview(
        self,
        actor_user_id: UUID,
        users: tuple[SyntheticFixtureUser, ...],
    ) -> SyntheticFixturePreview: ...

    def apply(
        self,
        command: SyntheticFixtureCommand,
        users: tuple[SyntheticFixtureUser, ...],
    ) -> SyntheticFixtureResult: ...

    def reconcile(
        self,
        command: SyntheticFixtureCommand,
        users: tuple[SyntheticFixtureUser, ...],
    ) -> SyntheticFixtureResult: ...
