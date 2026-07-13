"""Atomic and compatibility-safe ticket persistence operations."""

import logging
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

LOGGER = logging.getLogger(__name__)


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
        self._accept_many((committed,))
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
        return self.save_with_audits_if_current(
            expected,
            proposed,
            actor,
            ((event_type, metadata),),
        )

    def save_with_audits_if_current(
        self,
        expected: TicketRecord,
        proposed: TicketRecord,
        actor: UserAccount | UUID,
        events: tuple[tuple[str, dict[str, str]], ...],
    ) -> TicketRecord:
        if not events:
            raise ValueError("Audited ticket mutations require at least one audit event.")
        if self._transaction is not None:
            return self._commit(expected, proposed, actor, events)
        committed = replace(proposed, updated_at=datetime.now(UTC))
        confirmed = self._repository.save_if_current_with_confirmation(
            expected,
            committed,
            lambda: self._audit_log.record_many(
                tuple(
                    (event_type, str(_actor_id(actor)), metadata) for event_type, metadata in events
                )
            ),
        )
        if not confirmed:
            raise _ticket_changed()
        return committed

    def save_pair_audited(
        self,
        expected: tuple[TicketRecord, TicketRecord],
        proposed: tuple[TicketRecord, TicketRecord],
        event_type: str,
        actor: UserAccount | UUID,
        metadata: dict[str, str],
    ) -> tuple[TicketRecord, TicketRecord]:
        committed = tuple(replace(ticket, updated_at=datetime.now(UTC)) for ticket in proposed)
        if self._transaction is not None:
            audit = WorkflowAuditIntent(event_type, _actor_id(actor), metadata)
            if not self._transaction.commit_ticket_pair(
                expected, (committed[0], committed[1]), (audit,)
            ):
                raise _ticket_changed()
            self._accept_many(committed)
            return committed[0], committed[1]
        if not self._repository.save_pair_with_confirmation(
            expected,
            (committed[0], committed[1]),
            lambda: self._audit_log.record(event_type, str(_actor_id(actor)), metadata),
        ):
            raise _ticket_changed()
        return committed[0], committed[1]

    def restore_if_current(self, expected: TicketRecord, original: TicketRecord) -> bool:
        return self._repository.save_if_current(expected, original)

    def accept_committed(self, ticket: TicketRecord) -> None:
        self._repository.accept_committed(ticket)

    def _commit(
        self,
        expected: TicketRecord,
        proposed: TicketRecord,
        actor: UserAccount | UUID,
        events: tuple[tuple[str, dict[str, str]], ...],
    ) -> TicketRecord:
        committed = replace(proposed, updated_at=datetime.now(UTC))
        audits = tuple(
            WorkflowAuditIntent(event_type, _actor_id(actor), metadata)
            for event_type, metadata in events
        )
        if not self._transaction or not self._transaction.commit_ticket_update(
            expected, committed, audits
        ):
            raise _ticket_changed()
        self._accept_many((committed,))
        return committed

    def _accept_many(self, tickets: tuple[TicketRecord, ...]) -> None:
        for ticket in tickets:
            try:
                self.accept_committed(ticket)
            except Exception:
                LOGGER.exception(
                    "Durable ticket commit succeeded but the local cache refresh failed.",
                    extra={"ticket_id": str(ticket.ticket_id)},
                )
        try:
            self._audit_log.refresh_from_store()
        except Exception:
            LOGGER.exception("Durable audit commit succeeded but the local cache refresh failed.")


def _actor_id(actor: UserAccount | UUID) -> UUID:
    return actor.user_id if isinstance(actor, UserAccount) else actor


def _ticket_changed() -> AppError:
    return AppError(
        409,
        "ticket_changed",
        "The ticket changed while the operation was running. Retry the operation.",
    )
