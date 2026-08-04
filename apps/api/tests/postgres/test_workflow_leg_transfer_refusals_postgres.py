"""Evidence guards a cross-team workflow-leg transfer applies to a proposal."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from test_workflow_leg_transfers_postgres import _target_fixture, _upgrade_runtime
from work_package_handover_support import insert_handover_evidence

from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.domain.workflow_leg_transfers import (
    PackageTransferDisposition,
    PackageTransferPlan,
    ProposeWorkflowLegTransfer,
    WorkflowLegTransferConflict,
    WorkflowLegTransferDenied,
)
from coeus.persistence.workflow_leg_transfers_postgres import PostgresWorkflowLegTransferStore

pytestmark = pytest.mark.postgres


def _evidence(database_url: str) -> tuple[object, object, ProposeWorkflowLegTransfer]:
    _upgrade_runtime(database_url)
    source = insert_handover_evidence(database_url)
    engine = create_engine(database_url)
    target_manager, target_user, target_unit = uuid4(), uuid4(), uuid4()
    source_grant, target_grant, target_assign_grant, target_membership = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    start, end = _target_fixture(
        engine,
        source.actor_id,
        target_manager,
        target_user,
        target_unit,
        source_grant,
        target_grant,
        target_assign_grant,
        target_membership,
    )
    with engine.connect() as connection:
        ticket_version, ticket_hash = connection.execute(
            text("SELECT version,canonical_hash FROM coeus_ticket_aggregates WHERE ticket_id=:id"),
            {"id": source.ticket.ticket_id},
        ).one()
        packages = tuple(
            connection.execute(
                text(
                    "SELECT package_id,state,version FROM canonical_work_packages "
                    "WHERE ticket_id=:id AND workflow_leg='rfa' ORDER BY package_id"
                ),
                {"id": source.ticket.ticket_id},
            ).mappings()
        )
    plans = tuple(
        PackageTransferPlan(
            row["package_id"],
            PackageTransferDisposition.RETAIN
            if row["state"] == "complete"
            else PackageTransferDisposition.TRANSFER,
            int(row["version"]),
            None if row["state"] == "complete" else uuid4(),
            None if row["state"] == "complete" else "accepted-target-capacity",
            None if row["state"] == "complete" else start,
            None if row["state"] == "complete" else end,
            None if row["state"] == "complete" else 120,
        )
        for row in packages
    )
    proposal = ProposeWorkflowLegTransfer(
        uuid4(),
        source.ticket.ticket_id,
        WorkflowLeg.RFA,
        source.unit_id,
        target_unit,
        target_user,
        2,
        int(ticket_version),
        str(ticket_hash),
        source_grant,
        1,
        datetime.now(UTC) + timedelta(days=2),
        plans,
        "Reviewed workload balance",
    )
    return engine, source, proposal


def test_a_proposal_naming_another_source_team_is_unavailable(
    postgres_database_url: str,
) -> None:
    engine, source, proposal = _evidence(postgres_database_url)
    store = PostgresWorkflowLegTransferStore(engine)

    with pytest.raises(WorkflowLegTransferDenied, match="transfer is unavailable"):
        store.preview(source.actor_id, replace(proposal, source_unit_id=uuid4()))  # type: ignore[attr-defined]
    engine.dispose()  # type: ignore[attr-defined]


@pytest.mark.parametrize("field", ["expected_ownership_version", "expected_ticket_version"])
def test_stale_ownership_or_ticket_evidence_is_refused(
    postgres_database_url: str, field: str
) -> None:
    engine, source, proposal = _evidence(postgres_database_url)
    store = PostgresWorkflowLegTransferStore(engine)

    with pytest.raises((WorkflowLegTransferConflict, WorkflowLegTransferDenied)):
        store.preview(source.actor_id, replace(proposal, **{field: 99}))  # type: ignore[attr-defined]
    engine.dispose()  # type: ignore[attr-defined]


def test_a_changed_ticket_source_hash_is_refused(postgres_database_url: str) -> None:
    engine, source, proposal = _evidence(postgres_database_url)
    store = PostgresWorkflowLegTransferStore(engine)

    with pytest.raises(WorkflowLegTransferDenied, match="transfer is unavailable"):
        store.preview(source.actor_id, replace(proposal, expected_ticket_source_hash="a" * 64))  # type: ignore[attr-defined]
    engine.dispose()  # type: ignore[attr-defined]


@pytest.mark.parametrize("days", [-1, 45])
def test_an_expiry_outside_the_next_thirty_days_is_refused(
    postgres_database_url: str, days: int
) -> None:
    engine, source, proposal = _evidence(postgres_database_url)
    store = PostgresWorkflowLegTransferStore(engine)
    expires_at = datetime.now(UTC) + timedelta(days=days)

    with pytest.raises(WorkflowLegTransferConflict, match="within the next 30 days"):
        store.preview(source.actor_id, replace(proposal, expires_at=expires_at))  # type: ignore[attr-defined]
    engine.dispose()  # type: ignore[attr-defined]


def test_a_missing_or_stale_transfer_grant_is_refused(postgres_database_url: str) -> None:
    engine, source, proposal = _evidence(postgres_database_url)
    store = PostgresWorkflowLegTransferStore(engine)

    with pytest.raises(WorkflowLegTransferDenied, match="task transfer authority"):
        store.preview(source.actor_id, replace(proposal, authorising_grant_id=uuid4()))  # type: ignore[attr-defined]
    with pytest.raises(WorkflowLegTransferDenied, match="task transfer authority"):
        store.preview(source.actor_id, replace(proposal, expected_grant_version=9))  # type: ignore[attr-defined]
    with pytest.raises(WorkflowLegTransferDenied, match="task transfer authority"):
        store.preview(uuid4(), proposal)
    engine.dispose()  # type: ignore[attr-defined]


def test_a_dependant_package_missing_from_the_plan_is_refused(
    postgres_database_url: str,
) -> None:
    engine, source, proposal = _evidence(postgres_database_url)
    store = PostgresWorkflowLegTransferStore(engine)
    transferring = tuple(
        item
        for item in proposal.packages
        if item.disposition is PackageTransferDisposition.TRANSFER
    )

    with pytest.raises(WorkflowLegTransferConflict, match="needs a disposition"):
        store.preview(source.actor_id, replace(proposal, packages=transferring))  # type: ignore[attr-defined]
    engine.dispose()  # type: ignore[attr-defined]
