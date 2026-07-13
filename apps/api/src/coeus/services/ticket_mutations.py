"""Atomic and compatibility-safe ticket persistence operations."""

from contextlib import suppress
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from coeus.application.ports.tickets import TicketRepository
from coeus.application.ports.workflow_transaction import WorkflowTransactionPort
from coeus.core.errors import AppError
from coeus.domain.auth import UserAccount
from coeus.domain.tickets import TicketRecord
from coeus.domain.workflow_transaction import WorkflowAuditIntent
from coeus.services.audit import AuditLog
from coeus.services.ticket_persistence import save_ticket, save_ticket_if_current


class TicketMutationService:
    """Own ticket writes and their durable audit transaction boundary."""

    def __init__(
        self,
        repository: TicketRepository,
        audit_log: AuditLog,
        transaction: WorkflowTransactionPort | None = None,
    ) -> None:
        self._repository = repository
        self._audit_log = audit_log
        self._transaction = transaction

    def save(self, ticket: TicketRecord) -> TicketRecord:
        return save_ticket(self._repository, ticket)

    def create_audited(
        self,
        proposed: TicketRecord,
        event_type: str,
        actor: UserAccount | UUID,
        metadata: dict[str, str],
    ) -> TicketRecord:
        committed = replace(proposed, updated_at=datetime.now(UTC))
        if self._transaction is None:
            self._repository.save_with_confirmation(
                committed,
                lambda: self._audit_log.record(event_type, str(_actor_id(actor)), metadata),
            )
            return committed
        audit = WorkflowAuditIntent(event_type, _actor_id(actor), metadata)
        if not self._transaction.commit_ticket_create(committed, audit):
            raise AppError(409, "ticket_changed", "The ticket already exists.")
        with suppress(Exception):
            self.accept_committed(committed)
        with suppress(Exception):
            self._audit_log.refresh_from_store()
        return committed

    def save_if_current(self, expected: TicketRecord, proposed: TicketRecord) -> TicketRecord:
        return save_ticket_if_current(self._repository, expected, proposed)

    def save_audited_if_current(
        self,
        expected: TicketRecord,
        proposed: TicketRecord,
        event_type: str,
        actor: UserAccount | UUID,
        metadata: dict[str, str],
    ) -> TicketRecord:
        if self._transaction is not None:
            return self._commit(expected, proposed, event_type, actor, metadata)
        updated = self.save_if_current(expected, proposed)
        try:
            self._audit_log.record(event_type, str(_actor_id(actor)), metadata)
        except Exception:
            self.restore_if_current(updated, expected)
            raise
        return updated

    def restore_if_current(self, expected: TicketRecord, original: TicketRecord) -> bool:
        return self._repository.save_if_current(expected, original)

    def accept_committed(self, ticket: TicketRecord) -> None:
        self._repository.accept_committed(ticket)

    def _commit(
        self,
        expected: TicketRecord,
        proposed: TicketRecord,
        event_type: str,
        actor: UserAccount | UUID,
        metadata: dict[str, str],
    ) -> TicketRecord:
        committed = replace(proposed, updated_at=datetime.now(UTC))
        audit = WorkflowAuditIntent(event_type, _actor_id(actor), metadata)
        if not self._transaction or not self._transaction.commit_ticket_update(
            expected, committed, audit
        ):
            raise AppError(
                409,
                "ticket_changed",
                "The ticket changed while the operation was running. Retry the operation.",
            )
        with suppress(Exception):
            self.accept_committed(committed)
        with suppress(Exception):
            self._audit_log.refresh_from_store()
        return committed


def _actor_id(actor: UserAccount | UUID) -> UUID:
    return actor.user_id if isinstance(actor, UserAccount) else actor
