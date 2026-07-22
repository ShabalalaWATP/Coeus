"""Hosted dispatch branches for authority-fenced ticket mutations."""

from dataclasses import replace
from uuid import uuid4

import pytest

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.domain.workflow_authority import WorkflowCommitAuthority, WorkflowCommitResult
from coeus.domain.workflow_transaction import WorkflowAuditIntent
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.services.audit import AuditLog
from coeus.services.ticket_mutations import TicketMutationService


class _AuthorityTransaction:
    def __init__(self) -> None:
        self.create_result = WorkflowCommitResult.COMMITTED
        self.update_result = WorkflowCommitResult.COMMITTED
        self.created: TicketRecord | None = None
        self.updated: TicketRecord | None = None
        self.audits: tuple[WorkflowAuditIntent, ...] = ()

    def commit_authorised_ticket_create(
        self,
        ticket: TicketRecord,
        audit: WorkflowAuditIntent,
        _authority: WorkflowCommitAuthority,
    ) -> WorkflowCommitResult:
        self.created = ticket
        self.audits = (audit,)
        return self.create_result

    def commit_authorised_ticket_update(
        self,
        _expected: TicketRecord,
        updated: TicketRecord,
        audits: tuple[WorkflowAuditIntent, ...],
        _authority: WorkflowCommitAuthority,
    ) -> WorkflowCommitResult:
        self.updated = updated
        self.audits = audits
        return self.update_result


def test_hosted_authorised_create_and_update_accept_committed_state() -> None:
    repository = InMemoryTicketRepository()
    transaction = _AuthorityTransaction()
    service = TicketMutationService(repository, AuditLog(), transaction)  # type: ignore[arg-type]
    actor = _actor()
    authority = WorkflowCommitAuthority(actor, None, frozenset({Permission.CHAT_USE}))
    ticket = _ticket(actor)

    created = service.create_authorised_audited(ticket, "ticket_created", authority, {})
    updated = service.save_authorised_audited_if_current(
        created,
        replace(created, state=TicketState.INFO_REQUIRED),
        "ticket_updated",
        authority,
        {},
        (("secondary_event", {"source": "coverage"}),),
    )

    assert transaction.created == created
    assert transaction.updated == updated
    assert [audit.event_type for audit in transaction.audits] == [
        "ticket_updated",
        "secondary_event",
    ]
    assert repository.get(ticket.ticket_id) == updated


def test_hosted_authorised_create_maps_ticket_conflict() -> None:
    transaction = _AuthorityTransaction()
    transaction.create_result = WorkflowCommitResult.TICKET_CHANGED
    actor = _actor()
    service = TicketMutationService(
        InMemoryTicketRepository(),
        AuditLog(),
        transaction,  # type: ignore[arg-type]
    )

    with pytest.raises(AppError) as caught:
        service.create_authorised_audited(
            _ticket(actor),
            "ticket_created",
            WorkflowCommitAuthority(actor, None, frozenset({Permission.CHAT_USE})),
            {},
        )

    assert caught.value.code == "ticket_changed"


def _actor() -> UserAccount:
    return UserAccount(
        uuid4(),
        "authority-transaction@example.test",
        "Authority Transaction",
        frozenset({RoleName.USER}),
        frozenset({Permission.CHAT_USE}),
        "synthetic-hash",
        True,
        2,
    )


def _ticket(actor: UserAccount) -> TicketRecord:
    return TicketRecord(
        ticket_id=uuid4(),
        reference="TCK-AUTHORITY-BRANCH",
        requester_user_id=actor.user_id,
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(title="Synthetic authority branch"),
    )
