"""Transaction owner for release-sensitive workflow persistence."""

from typing import Protocol
from uuid import UUID

from coeus.domain.store import StoreProduct
from coeus.domain.submission_authority import SubmissionCommitResult
from coeus.domain.tickets import TicketRecord
from coeus.domain.workflow_authority import WorkflowCommitAuthority, WorkflowCommitResult
from coeus.domain.workflow_transaction import (
    ReleaseNotificationIntent,
    WorkflowAuditIntent,
    WorkflowOutboxIntent,
)


class WorkflowTransactionPort(Protocol):
    def commit_ticket_create(
        self,
        ticket: TicketRecord,
        audit: WorkflowAuditIntent,
    ) -> bool: ...

    def commit_authorised_ticket_create(
        self,
        ticket: TicketRecord,
        audit: WorkflowAuditIntent,
        authority: WorkflowCommitAuthority,
    ) -> WorkflowCommitResult: ...

    def commit_ticket_update(
        self,
        expected: TicketRecord,
        updated: TicketRecord,
        audits: tuple[WorkflowAuditIntent, ...],
        outbox: tuple[WorkflowOutboxIntent, ...] = (),
    ) -> bool: ...

    def commit_authorised_ticket_update(
        self,
        expected: TicketRecord,
        updated: TicketRecord,
        audits: tuple[WorkflowAuditIntent, ...],
        authority: WorkflowCommitAuthority,
        outbox: tuple[WorkflowOutboxIntent, ...] = (),
    ) -> WorkflowCommitResult: ...

    def commit_ticket_pair(
        self,
        expected: tuple[TicketRecord, TicketRecord],
        updated: tuple[TicketRecord, TicketRecord],
        audits: tuple[WorkflowAuditIntent, ...],
    ) -> bool: ...

    def commit_product_submission(
        self,
        expected: TicketRecord,
        updated: TicketRecord,
        audits: tuple[WorkflowAuditIntent, ...],
        actor_user_id: UUID,
        required_acg_ids: frozenset[UUID],
    ) -> SubmissionCommitResult: ...

    def commit_qc_release(
        self,
        expected: TicketRecord,
        updated: TicketRecord,
        product: StoreProduct,
        audit: WorkflowAuditIntent,
        notification: ReleaseNotificationIntent | None,
    ) -> bool: ...

    def commit_authorised_qc_release(
        self,
        expected: TicketRecord,
        updated: TicketRecord,
        product: StoreProduct,
        audit: WorkflowAuditIntent,
        notification: ReleaseNotificationIntent | None,
        authority: WorkflowCommitAuthority,
    ) -> WorkflowCommitResult: ...
