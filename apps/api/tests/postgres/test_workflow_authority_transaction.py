"""PostgreSQL commit-time workflow-authority coverage."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine, text

from coeus.core.config import Settings
from coeus.core.permissions import Permission
from coeus.domain.auth import SessionRecord
from coeus.domain.enums import TicketState
from coeus.domain.teams import TeamKind
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.domain.workflow_authority import (
    QcCommitAuthority,
    RfiCommitAuthority,
    WorkflowCommitAuthority,
    WorkflowCommitResult,
)
from coeus.domain.workflow_transaction import WorkflowAuditIntent
from coeus.main import create_app
from coeus.persistence.codec import decode_value
from coeus.persistence.database_url import synchronous_database_url

pytestmark = pytest.mark.postgres


def test_authorised_update_rejects_revoked_actor_then_accepts_current_actor(
    postgres_database_url: str,
) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            database_url=postgres_database_url,
            persistence_provider="postgres",
            ticket_persistence_mode="relational",
            seed_demo_content=False,
        )
    )
    access = app.state.access_services.repository
    actor = access.get_user_by_username("user@example.test")
    assert actor is not None
    ticket = TicketRecord(
        ticket_id=uuid4(),
        reference="TCK-WORKFLOW-AUTHORITY",
        requester_user_id=actor.user_id,
        state=TicketState.RFI_SEARCHING,
        intake=IntakeDetails(title="Synthetic workflow authority"),
    )
    repository = app.state.ticket_services.tickets._repository
    repository.save(ticket)
    updated = replace(ticket, state=TicketState.RFI_NO_MATCH)
    audit = WorkflowAuditIntent(
        "rfi_search_completed",
        actor.user_id,
        {"ticket_id": str(ticket.ticket_id)},
    )
    app.state.user_admin_service._users.save(replace(actor, is_active=False))

    denied = app.state.workflow_transaction.commit_authorised_ticket_update(
        ticket,
        updated,
        (audit,),
        WorkflowCommitAuthority(actor, None, frozenset({Permission.RFI_SEARCH})),
    )

    assert denied is WorkflowCommitResult.AUTHORITY_REVOKED
    assert _stored_ticket(postgres_database_url, ticket.ticket_id) == ticket
    assert _audit_count(postgres_database_url) == 0

    app.state.user_admin_service._users.save(replace(actor, is_active=True))
    current = access.get_user(actor.user_id)
    assert current is not None
    committed = app.state.workflow_transaction.commit_authorised_ticket_update(
        ticket,
        updated,
        (audit,),
        WorkflowCommitAuthority(current, None, frozenset({Permission.RFI_SEARCH})),
    )

    assert committed is WorkflowCommitResult.COMMITTED
    assert _stored_ticket(postgres_database_url, ticket.ticket_id) == updated
    assert _audit_count(postgres_database_url) == 1


def test_authorised_update_rejects_a_revoked_exact_session(
    postgres_database_url: str,
) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            database_url=postgres_database_url,
            persistence_provider="postgres",
            ticket_persistence_mode="relational",
            seed_demo_content=False,
        )
    )
    actor = app.state.access_services.repository.get_user_by_username("user@example.test")
    assert actor is not None
    session = SessionRecord(
        session_id="synthetic-workflow-session",
        user_id=actor.user_id,
        csrf_token="synthetic-csrf",  # noqa: S106
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        created_at=datetime.now(UTC),
        credential_version=actor.credential_version,
    )
    sessions = app.state.auth_service._sessions
    sessions.save(session)
    ticket = TicketRecord(
        ticket_id=uuid4(),
        reference="TCK-WORKFLOW-SESSION",
        requester_user_id=actor.user_id,
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(title="Synthetic exact-session authority"),
    )
    repository = app.state.ticket_services.tickets._repository
    repository.save(ticket)
    updated = replace(ticket, intake=IntakeDetails(title="Rejected stale session"))
    audit = WorkflowAuditIntent(
        "ticket_chat_message_received",
        actor.user_id,
        {"ticket_id": str(ticket.ticket_id)},
    )
    authority = WorkflowCommitAuthority(
        actor,
        session,
        frozenset({Permission.CHAT_USE}),
    )
    deleted_session = sessions.delete(session.session_id)
    assert deleted_session == session

    denied = app.state.workflow_transaction.commit_authorised_ticket_update(
        ticket,
        updated,
        (audit,),
        authority,
    )

    assert denied is WorkflowCommitResult.AUTHORITY_REVOKED
    assert _stored_ticket(postgres_database_url, ticket.ticket_id) == ticket
    assert _audit_count(postgres_database_url) == 0

    sessions.save(session)
    committed = app.state.workflow_transaction.commit_authorised_ticket_update(
        ticket,
        updated,
        (audit,),
        authority,
    )

    assert committed is WorkflowCommitResult.COMMITTED
    assert _stored_ticket(postgres_database_url, ticket.ticket_id) == updated
    assert _audit_count(postgres_database_url) == 1


def test_authorised_update_revalidates_requester_acgs(
    postgres_database_url: str,
) -> None:
    app = _postgres_app(postgres_database_url)
    access = app.state.access_services.repository
    actor = access.get_user_by_username("user@example.test")
    requester = access.get_user_by_username("colleague@example.test")
    assert actor is not None and requester is not None
    requester_acgs = access.active_acg_ids_for_user(requester.user_id)
    revoked_acg = next(iter(requester_acgs))
    ticket = _ticket(app, requester.user_id, "TCK-RFI-ACG", TicketState.RFI_SEARCHING)
    updated = replace(ticket, state=TicketState.RFI_NO_MATCH)
    audit = _audit(ticket, actor.user_id, "rfi_search_completed")
    authority = WorkflowCommitAuthority(
        actor,
        None,
        frozenset({Permission.RFI_SEARCH}),
        rfi=RfiCommitAuthority(requester, requester_acgs, frozenset()),
    )
    access.remove_membership(revoked_acg, requester.user_id)

    denied = app.state.workflow_transaction.commit_authorised_ticket_update(
        ticket, updated, (audit,), authority
    )

    assert denied is WorkflowCommitResult.AUTHORITY_REVOKED
    assert _stored_ticket(postgres_database_url, ticket.ticket_id) == ticket
    assert _audit_count(postgres_database_url) == 0

    access.add_membership(revoked_acg, requester.user_id)
    committed = app.state.workflow_transaction.commit_authorised_ticket_update(
        ticket, updated, (audit,), authority
    )

    assert committed is WorkflowCommitResult.COMMITTED
    assert _stored_ticket(postgres_database_url, ticket.ticket_id) == updated
    assert _audit_count(postgres_database_url) == 1


def test_authorised_update_revalidates_qc_team_and_release_acgs(
    postgres_database_url: str,
) -> None:
    app = _postgres_app(postgres_database_url)
    access = app.state.access_services.repository
    actor = access.get_user_by_username("qc.manager@example.test")
    assert actor is not None
    release_acg_id = next(iter(access.active_acg_ids_for_user(actor.user_id)))
    release_acg = access.get_acg(release_acg_id)
    assert release_acg is not None
    qc_session = SessionRecord(
        session_id=f"qc-session-{uuid4()}",
        user_id=actor.user_id,
        csrf_token="synthetic-qc-csrf",  # noqa: S106
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        created_at=datetime.now(UTC),
        credential_version=actor.credential_version,
    )
    sessions = app.state.auth_service._sessions
    sessions.save(qc_session)
    team_repository = app.state.team_repository
    qc_team = next(team for team in team_repository.list_teams() if team.kind is TeamKind.QC)
    ticket = _ticket(app, actor.user_id, "TCK-QC-AUTHORITY", TicketState.QC_REVIEW)
    updated = replace(ticket, state=TicketState.DISSEMINATION_READY)
    audit = _audit(ticket, actor.user_id, "product_released")
    authority = WorkflowCommitAuthority(
        actor,
        qc_session,
        frozenset({Permission.QC_APPROVE}),
        qc=QcCommitAuthority(0, frozenset(), 0, frozenset({release_acg_id}), None),
    )
    deleted_qc_session = sessions.delete(qc_session.session_id)
    assert deleted_qc_session == qc_session
    session_denied = app.state.workflow_transaction.commit_authorised_ticket_update(
        ticket, updated, (audit,), authority
    )
    assert session_denied is WorkflowCommitResult.AUTHORITY_REVOKED
    assert _stored_ticket(postgres_database_url, ticket.ticket_id) == ticket
    assert _audit_count(postgres_database_url) == 0

    sessions.save(qc_session)
    team_repository.save_team(
        replace(
            qc_team,
            manager_user_ids=tuple(
                user_id for user_id in qc_team.manager_user_ids if user_id != actor.user_id
            ),
            member_user_ids=tuple(
                user_id for user_id in qc_team.member_user_ids if user_id != actor.user_id
            ),
        )
    )

    team_denied = app.state.workflow_transaction.commit_authorised_ticket_update(
        ticket, updated, (audit,), authority
    )
    assert team_denied is WorkflowCommitResult.AUTHORITY_REVOKED
    assert _stored_ticket(postgres_database_url, ticket.ticket_id) == ticket
    assert _audit_count(postgres_database_url) == 0

    team_repository.save_team(qc_team)
    access.save_acg(replace(release_acg, is_active=False))
    acg_denied = app.state.workflow_transaction.commit_authorised_ticket_update(
        ticket, updated, (audit,), authority
    )
    assert acg_denied is WorkflowCommitResult.AUTHORITY_REVOKED
    assert _stored_ticket(postgres_database_url, ticket.ticket_id) == ticket
    assert _audit_count(postgres_database_url) == 0

    access.save_acg(release_acg)
    committed = app.state.workflow_transaction.commit_authorised_ticket_update(
        ticket, updated, (audit,), authority
    )
    assert committed is WorkflowCommitResult.COMMITTED
    assert _stored_ticket(postgres_database_url, ticket.ticket_id) == updated
    assert _audit_count(postgres_database_url) == 1


def _postgres_app(database_url: str) -> FastAPI:
    return create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            database_url=database_url,
            persistence_provider="postgres",
            ticket_persistence_mode="relational",
            seed_demo_content=False,
        )
    )


def _ticket(
    app: FastAPI,
    requester_id: UUID,
    reference: str,
    state: TicketState,
) -> TicketRecord:
    ticket = TicketRecord(
        ticket_id=uuid4(),
        reference=reference,
        requester_user_id=requester_id,
        state=state,
        intake=IntakeDetails(title="Synthetic mutable workflow authority"),
    )
    app.state.ticket_services.tickets._repository.save(ticket)
    return ticket


def _audit(ticket: TicketRecord, actor_id: UUID, event_type: str) -> WorkflowAuditIntent:
    return WorkflowAuditIntent(event_type, actor_id, {"ticket_id": str(ticket.ticket_id)})


def _stored_ticket(database_url: str, ticket_id: UUID) -> TicketRecord:
    with create_engine(synchronous_database_url(database_url)).connect() as connection:
        payload = connection.execute(
            text(
                "SELECT payload FROM coeus_ticket_aggregates "
                "WHERE ticket_id = CAST(:ticket_id AS uuid)"
            ),
            {"ticket_id": str(ticket_id)},
        ).scalar_one()
    value = decode_value(dict(payload))
    assert isinstance(value, TicketRecord)
    return value


def _audit_count(database_url: str) -> int:
    with create_engine(synchronous_database_url(database_url)).connect() as connection:
        return int(connection.execute(text("SELECT count(*) FROM coeus_audit_events")).scalar_one())
