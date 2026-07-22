"""Decision-table coverage for protected workflow commit authority."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, SessionRecord, UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.domain.workflow_authority import (
    WorkflowCommitAuthority,
    WorkflowCommitResult,
    workflow_authority_result,
)
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.services.audit import AuditLog
from coeus.services.ticket_mutations import TicketMutationService


def test_workflow_authority_requires_the_exact_active_actor_and_permissions() -> None:
    actor = UserAccount(
        user_id=uuid4(),
        username="workflow.actor@example.test",
        display_name="Workflow Actor",
        roles=frozenset({RoleName.USER}),
        permissions=frozenset({Permission.CHAT_USE, Permission.RFI_SEARCH, Permission.QC_APPROVE}),
        password_hash="synthetic-hash",  # noqa: S106
        is_active=True,
        clearance_level=1,
    )
    required = WorkflowCommitAuthority(actor, None, frozenset({Permission.RFI_SEARCH}))

    assert _result((actor,), required) is WorkflowCommitResult.COMMITTED
    assert _result((), required) is WorkflowCommitResult.AUTHORITY_REVOKED
    assert _result((replace(actor, is_active=False),), required) is (
        WorkflowCommitResult.AUTHORITY_REVOKED
    )
    assert _result((replace(actor, display_name="Changed"),), required) is (
        WorkflowCommitResult.AUTHORITY_REVOKED
    )
    assert (
        _result((replace(actor, permissions=frozenset({Permission.CHAT_USE})),), required)
        is WorkflowCommitResult.AUTHORITY_REVOKED
    )


def test_active_work_allows_an_exact_active_actor_without_extra_permission() -> None:
    actor = UserAccount(
        user_id=uuid4(),
        username="active-work@example.test",
        display_name="Active Work",
        roles=frozenset(),
        permissions=frozenset(),
        password_hash="synthetic-hash",  # noqa: S106
        is_active=True,
        clearance_level=1,
    )

    result = _result((actor,), WorkflowCommitAuthority(actor, None, frozenset()))

    assert result is WorkflowCommitResult.COMMITTED


def test_workflow_authority_requires_the_exact_unexpired_session() -> None:
    actor = _actor()
    session = SessionRecord(
        session_id="session-hash",
        user_id=actor.user_id,
        csrf_token="csrf",  # noqa: S106
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        created_at=datetime.now(UTC),
    )
    authority = WorkflowCommitAuthority(actor, session, frozenset({Permission.CHAT_USE}))

    assert _result((actor,), authority, (session,)) is WorkflowCommitResult.COMMITTED
    assert _result((actor,), authority) is WorkflowCommitResult.AUTHORITY_REVOKED
    changed = replace(session, csrf_token="changed")  # noqa: S106
    assert _result((actor,), authority, (changed,)) is (WorkflowCommitResult.AUTHORITY_REVOKED)


def test_authorised_mutations_fail_closed_without_a_commit_boundary() -> None:
    actor = UserAccount(
        user_id=uuid4(),
        username="unfenced@example.test",
        display_name="Unfenced",
        roles=frozenset({RoleName.USER}),
        permissions=frozenset({Permission.CHAT_USE}),
        password_hash="synthetic-hash",  # noqa: S106
        is_active=True,
        clearance_level=1,
    )
    repository = InMemoryTicketRepository()
    mutations = TicketMutationService(repository, AuditLog())
    authority = WorkflowCommitAuthority(actor, None, frozenset({Permission.CHAT_USE}))
    ticket = TicketRecord(
        ticket_id=uuid4(),
        reference="TCK-UNFENCED",
        requester_user_id=actor.user_id,
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(),
    )

    with pytest.raises(RuntimeError, match="authority commit boundary"):
        mutations.create_authorised_audited(
            ticket,
            "ticket_chat_message_received",
            authority,
            {"ticket_id": str(ticket.ticket_id)},
        )

    repository.save(ticket)
    with pytest.raises(RuntimeError, match="authority commit boundary"):
        mutations.save_authorised_audited_if_current(
            ticket,
            replace(ticket, reference="TCK-UNFENCED-UPDATED"),
            "ticket_chat_message_received",
            authority,
            {"ticket_id": str(ticket.ticket_id)},
        )
    confirmed = False

    def confirm() -> None:
        nonlocal confirmed
        confirmed = True

    with pytest.raises(RuntimeError, match="authority commit boundary"):
        mutations.save_authorised_if_current_with_confirmation(
            ticket,
            replace(ticket, reference="TCK-UNFENCED-QC"),
            authority,
            confirm,
        )
    assert repository.get(ticket.ticket_id) == ticket
    assert not confirmed


def _result(
    users: tuple[UserAccount, ...],
    authority: WorkflowCommitAuthority,
    sessions: tuple[SessionRecord, ...] = (),
) -> WorkflowCommitResult:
    return workflow_authority_result(
        users,
        sessions,
        (),
        (),
        (),
        (),
        authority,
    )


def _actor() -> UserAccount:
    return UserAccount(
        user_id=uuid4(),
        username="session@example.test",
        display_name="Session Actor",
        roles=frozenset({RoleName.USER}),
        permissions=frozenset({Permission.CHAT_USE}),
        password_hash="synthetic-hash",  # noqa: S106
        is_active=True,
        clearance_level=1,
    )
