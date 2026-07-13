"""Transaction owner for release-sensitive workflow persistence."""

from typing import Protocol

from coeus.domain.store import StoreProduct
from coeus.domain.tickets import TicketRecord
from coeus.domain.workflow_transaction import ReleaseNotificationIntent, WorkflowAuditIntent


class WorkflowTransactionPort(Protocol):
    def commit_ticket_create(
        self,
        ticket: TicketRecord,
        audit: WorkflowAuditIntent,
    ) -> bool: ...

    def commit_ticket_update(
        self,
        expected: TicketRecord,
        updated: TicketRecord,
        audits: tuple[WorkflowAuditIntent, ...],
    ) -> bool: ...

    def commit_ticket_pair(
        self,
        expected: tuple[TicketRecord, TicketRecord],
        updated: tuple[TicketRecord, TicketRecord],
        audits: tuple[WorkflowAuditIntent, ...],
    ) -> bool: ...

    def commit_qc_release(
        self,
        expected: TicketRecord,
        updated: TicketRecord,
        product: StoreProduct,
        audit: WorkflowAuditIntent,
        notification: ReleaseNotificationIntent | None,
    ) -> bool: ...
