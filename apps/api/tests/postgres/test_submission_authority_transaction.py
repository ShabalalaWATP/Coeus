"""PostgreSQL commit-time submission authority coverage."""

from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from coeus.core.config import Settings
from coeus.domain.enums import TicketState
from coeus.domain.submission_authority import SubmissionCommitResult
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.domain.workflow_transaction import WorkflowAuditIntent
from coeus.main import create_app
from coeus.persistence.database_url import synchronous_database_url

pytestmark = pytest.mark.postgres


def test_submission_commit_rejects_revoked_acg_and_preserves_valid_upload(
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
    actor = access.get_user_by_username("analyst@example.test")
    assert actor is not None
    acg_id = next(acg.acg_id for acg in access.list_acgs() if acg.code == "ACG-EU-CYBER")
    ticket = TicketRecord(
        ticket_id=uuid4(),
        reference="TCK-SUBMISSION-AUTHORITY",
        requester_user_id=uuid4(),
        state=TicketState.ANALYST_IN_PROGRESS,
        intake=IntakeDetails(title="Synthetic submission authority"),
    )
    app.state.ticket_services.tickets._repository.save(ticket)
    updated = replace(ticket, state=TicketState.REWORK_REQUIRED)
    audit = WorkflowAuditIntent(
        "product_submission_uploaded",
        actor.user_id,
        {"ticket_id": str(ticket.ticket_id)},
    )
    access.remove_membership(acg_id, actor.user_id)

    denied = app.state.workflow_transaction.commit_product_submission(
        ticket, updated, (audit,), actor.user_id, frozenset({acg_id})
    )

    assert denied is SubmissionCommitResult.ACG_NOT_AUTHORISED
    assert app.state.ticket_services.tickets._repository.get(ticket.ticket_id) == ticket
    with create_engine(synchronous_database_url(postgres_database_url)).connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM coeus_audit_events")).scalar_one() == 0

    access.add_membership(acg_id, actor.user_id)
    committed = app.state.workflow_transaction.commit_product_submission(
        ticket, updated, (audit,), actor.user_id, frozenset({acg_id})
    )

    assert committed is SubmissionCommitResult.COMMITTED
    restored = app.state.ticket_services.tickets._repository
    restored.accept_committed(updated)
    assert restored.get(ticket.ticket_id) == updated
    with create_engine(synchronous_database_url(postgres_database_url)).connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM coeus_audit_events")).scalar_one() == 1

    stale = app.state.workflow_transaction.commit_product_submission(
        ticket,
        replace(ticket, state=TicketState.CANCELLED),
        (audit,),
        actor.user_id,
        frozenset({acg_id}),
    )

    assert stale is SubmissionCommitResult.TICKET_CHANGED
    with create_engine(synchronous_database_url(postgres_database_url)).connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM coeus_audit_events")).scalar_one() == 1
