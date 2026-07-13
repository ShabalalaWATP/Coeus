from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from coeus.domain.draft_audience import DraftAudienceReason
from coeus.domain.enums import TicketState
from coeus.domain.tickets import (
    AnalystAssignment,
    IntakeDetails,
    LinkedAnalystProduct,
    RoutingRoute,
    TicketRecord,
)
from coeus.persistence.draft_audience_reconciliation import reconcile_draft_audiences
from coeus.persistence.state_store import PostgresStateStore
from coeus.repositories.tickets import InMemoryTicketRepository

pytestmark = pytest.mark.postgres


def _ticket(database_url: str) -> tuple[TicketRecord, object, object, object, object]:
    ticket_id, analyst_id, manager_id, reviewer_id, product_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    assignment = AnalystAssignment(
        assignment_id=uuid4(),
        ticket_id=ticket_id,
        analyst_user_id=analyst_id,
        assigned_by_user_id=manager_id,
        route=RoutingRoute.RFA,
        created_at=datetime.now(UTC),
    )
    link = LinkedAnalystProduct(
        link_id=uuid4(),
        ticket_id=ticket_id,
        product_id=product_id,
        reference="PROD-RECONCILE",
        title="Audience reconciliation",
        summary="Synthetic relationship",
        linked_by_user_id=analyst_id,
        created_at=datetime.now(UTC),
    )
    ticket = TicketRecord(
        ticket_id=ticket_id,
        reference="TCK-RECONCILE",
        requester_user_id=uuid4(),
        state=TicketState.QC_REVIEW,
        intake=IntakeDetails(title="Audience reconciliation"),
        analyst_assignments=(assignment,),
        linked_products=(link,),
        qc_reviewer_user_id=reviewer_id,
        qc_claimed_at=datetime.now(UTC),
    )
    InMemoryTicketRepository(PostgresStateStore(database_url, "relational")).save(ticket)
    return ticket, analyst_id, manager_id, reviewer_id, product_id


def test_dry_run_and_apply_converge_without_duplicate_audit(
    postgres_database_url: str,
) -> None:
    ticket, analyst_id, manager_id, reviewer_id, product_id = _ticket(postgres_database_url)
    engine = create_engine(postgres_database_url)
    extra_principal = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "DELETE FROM coeus_draft_audiences WHERE principal_id=:analyst AND reason=:reason"
            ),
            {"analyst": analyst_id, "reason": DraftAudienceReason.ASSIGNED_ANALYST.value},
        )
        connection.execute(
            text(
                "INSERT INTO coeus_draft_audiences(product_id,principal_id,reason,ticket_id) "
                "VALUES (:product,:principal,:reason,:ticket)"
            ),
            {
                "product": product_id,
                "principal": extra_principal,
                "reason": DraftAudienceReason.QUALITY_CONTROL.value,
                "ticket": ticket.ticket_id,
            },
        )

    dry_run = reconcile_draft_audiences(postgres_database_url)

    assert dry_run.expected_count == 3
    assert dry_run.actual_count == 3
    assert len(dry_run.missing) == 1
    assert len(dry_run.extra) == 1
    assert dry_run.changed_count == 0

    applied = reconcile_draft_audiences(
        postgres_database_url,
        apply=True,
        operator="operator-1",
        reason="cutover reconciliation",
    )

    assert applied.missing == ()
    assert applied.extra == ()
    assert applied.changed_count == 2
    with engine.connect() as connection:
        rows = set(
            connection.execute(
                text("SELECT principal_id::text, reason FROM coeus_draft_audiences")
            ).all()
        )
        assert rows == {
            (str(analyst_id), DraftAudienceReason.ASSIGNED_ANALYST.value),
            (str(manager_id), DraftAudienceReason.RESPONSIBLE_MANAGER.value),
            (str(reviewer_id), DraftAudienceReason.QUALITY_CONTROL.value),
        }
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM coeus_audit_events "
                    "WHERE event_type='draft_audience_reconciled'"
                )
            ).scalar_one()
            == 1
        )

    repeated = reconcile_draft_audiences(
        postgres_database_url,
        apply=True,
        operator="operator-1",
        reason="idempotence check",
    )
    assert repeated.changed_count == 0
    with engine.connect() as connection:
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM coeus_audit_events "
                    "WHERE event_type='draft_audience_reconciled'"
                )
            ).scalar_one()
            == 1
        )
