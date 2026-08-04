"""Application port for scheduled and immediate personnel transfers."""

from datetime import datetime
from typing import Protocol

from coeus.domain.organisation_transfer import (
    PersonnelTransferCommand,
    PersonnelTransferImpact,
    PersonnelTransferRequest,
    PersonnelTransferResult,
)


class OrganisationTransferStore(Protocol):
    def inspect(self, request: PersonnelTransferRequest) -> PersonnelTransferImpact: ...

    def replay(self, command: PersonnelTransferCommand) -> PersonnelTransferResult | None: ...

    def apply(self, command: PersonnelTransferCommand) -> PersonnelTransferResult: ...

    def due(
        self, effective_at: datetime, *, limit: int = 100
    ) -> tuple[PersonnelTransferCommand, ...]: ...

    def activate(self, command: PersonnelTransferCommand) -> PersonnelTransferResult: ...

    def block(
        self, command: PersonnelTransferCommand, failure_code: str
    ) -> PersonnelTransferResult: ...
