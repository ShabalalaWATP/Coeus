"""Application boundary for JIOC routing orchestration."""

from typing import Protocol, runtime_checkable
from uuid import UUID

from coeus.domain.tickets import TicketRecord


@runtime_checkable
class JiocRoutingService(Protocol):
    def route(self, ticket_id: UUID, *, apply: bool = True) -> TicketRecord: ...

    def defer_to_manager(
        self, ticket_id: UUID, reason: str = "routing_automation_disabled"
    ) -> TicketRecord: ...
