"""Authoritative ticket-assignment regressions for package handover."""

from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from coeus.domain.work_package_handovers import (
    HandoverWorkPackageCommand,
    WorkPackageHandoverDenied,
)
from coeus.persistence.codec import encode_value
from coeus.persistence.state_store import PostgresStateStore
from coeus.persistence.work_package_handovers_postgres import (
    PostgresWorkPackageHandoverStore,
)
from postgres.work_package_handover_support import (
    insert_handover_evidence,
    upgrade_handover_schema,
)

pytestmark = pytest.mark.postgres


def test_assignment_revocation_after_preview_denies_and_preserves_source(
    postgres_database_url: str,
) -> None:
    upgrade_handover_schema(postgres_database_url)
    evidence = insert_handover_evidence(postgres_database_url)
    engine = create_engine(postgres_database_url)
    store = PostgresWorkPackageHandoverStore(engine)
    preview = store.preview(evidence.actor_id, evidence.request)
    revoked = replace(
        evidence.ticket,
        analyst_assignments=tuple(
            replace(item, active=False) for item in evidence.ticket.analyst_assignments
        ),
    )
    PostgresStateStore(postgres_database_url, "relational").save_ticket_record(
        encode_value(revoked), 1
    )

    with pytest.raises(WorkPackageHandoverDenied):
        store.execute(
            HandoverWorkPackageCommand(
                uuid4(),
                "assignment-drift",
                evidence.actor_id,
                evidence.request,
                preview.preview_hash,
            )
        )

    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT package.accountable_user_id,reservation.state "
                "FROM canonical_work_packages package JOIN capacity_reservations reservation "
                "ON reservation.package_id=package.package_id "
                "WHERE package.package_id=:package AND reservation.reservation_id=:reservation"
            ),
            {"package": evidence.package_id, "reservation": evidence.reservation_id},
        ).one()
        command_count = connection.execute(
            text("SELECT count(*) FROM work_package_handover_commands WHERE package_id=:package"),
            {"package": evidence.package_id},
        ).scalar_one()
    assert tuple(row) == (evidence.owner_id, "active")
    assert command_count == 0
    engine.dispose()
