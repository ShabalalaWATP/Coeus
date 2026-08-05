"""Real PostgreSQL acceptance and access evidence for cross-team work transfer."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.domain.workflow_leg_transfers import (
    PackageTransferDisposition,
    PackageTransferPlan,
    ProposeWorkflowLegTransfer,
    WorkflowLegTransferCommand,
    WorkflowLegTransferDenied,
)
from coeus.persistence.workflow_leg_transfers_postgres import PostgresWorkflowLegTransferStore
from postgres.test_workflow_leg_transfer_migration_postgres import _upgrade
from postgres.work_package_handover_support import insert_handover_evidence

pytestmark = pytest.mark.postgres
API_ROOT = Path(__file__).resolve().parents[2]


def test_two_managers_move_work_without_moving_people(postgres_database_url: str) -> None:
    _upgrade_runtime(postgres_database_url)
    source = insert_handover_evidence(postgres_database_url)
    engine = create_engine(postgres_database_url)
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
            text("""SELECT version,canonical_hash
FROM coeus_ticket_aggregates WHERE ticket_id=:id"""),
            {"id": source.ticket.ticket_id},
        ).one()
        packages = tuple(
            connection.execute(
                text("""SELECT package_id,state,version
FROM canonical_work_packages WHERE ticket_id=:id AND workflow_leg='rfa' ORDER BY package_id"""),
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
    store = PostgresWorkflowLegTransferStore(engine)
    preview = store.preview(source.actor_id, proposal)
    proposed = store.propose(
        source.actor_id, uuid4(), "propose-transfer", proposal, preview.preview_hash
    )
    accepted = store.decide(
        WorkflowLegTransferCommand(
            uuid4(),
            "accept-transfer",
            target_manager,
            proposal.transfer_id,
            proposed.version,
            "accept",
            preview.preview_hash,
            target_grant,
            1,
            target_membership,
            1,
            1,
            "d" * 64,
            target_assign_grant,
            1,
            "Receiving team accepts",
        )
    )
    replay = store.decide(
        WorkflowLegTransferCommand(
            uuid4(),
            "accept-transfer",
            target_manager,
            proposal.transfer_id,
            proposed.version,
            "accept",
            preview.preview_hash,
            target_grant,
            1,
            target_membership,
            1,
            1,
            "d" * 64,
            target_assign_grant,
            1,
            "Receiving team accepts",
        )
    )
    assert accepted.state.value == "accepted" and replay.replayed
    with engine.connect() as connection:
        ownership = connection.execute(
            text("""SELECT owning_unit_id FROM team_task_ownership
WHERE ticket_id=:id AND workflow_leg='rfa'"""),
            {"id": source.ticket.ticket_id},
        ).scalar_one()
        package = connection.execute(
            text("""SELECT owning_unit_id,accountable_user_id
FROM canonical_work_packages WHERE package_id=:id"""),
            {"id": source.package_id},
        ).one()
        source_membership_count = connection.execute(
            text("""SELECT count(*) FROM team_memberships
WHERE user_id=:user AND unit_id=:unit AND state='active'"""),
            {"user": source.target_id, "unit": source.unit_id},
        ).scalar_one()
        evidence = connection.execute(
            text("""SELECT
(SELECT count(*) FROM workflow_leg_transfer_team_holds WHERE transfer_id=:id),
(SELECT count(*) FROM capacity_reservations WHERE package_id=:package AND user_id=:target
 AND state IN ('held','active')),
(SELECT count(*) FROM coeus_outbox WHERE event_type='workflow_leg_transfer_accepted')"""),
            {"id": proposal.transfer_id, "package": source.package_id, "target": target_user},
        ).one()
    assert ownership == target_unit and tuple(package) == (target_unit, target_user)
    assert source_membership_count == 1
    assert tuple(evidence) == (1, 1, 1)
    engine.dispose()


def test_unrelated_manager_cannot_decide_transfer(postgres_database_url: str) -> None:
    _upgrade_runtime(postgres_database_url)
    engine = create_engine(postgres_database_url)
    store = PostgresWorkflowLegTransferStore(engine)
    with pytest.raises(WorkflowLegTransferDenied, match="unavailable"):
        store.decide(
            WorkflowLegTransferCommand(
                uuid4(),
                "probe-transfer",
                uuid4(),
                uuid4(),
                1,
                "reject",
                grant_id=uuid4(),
                expected_grant_version=1,
            )
        )
    engine.dispose()


def _target_fixture(
    engine: Engine,
    source_manager: object,
    target_manager: object,
    target_user: object,
    target_unit: object,
    source_grant: object,
    target_grant: object,
    target_assign_grant: object,
    membership: object,
) -> tuple[datetime, datetime]:
    with engine.begin() as connection:
        now = connection.execute(text("SELECT transaction_timestamp()")).scalar_one()
        zone = ZoneInfo("Europe/London")
        day = datetime.now(zone).date() + timedelta(days=1)
        while day.weekday() > 4:
            day += timedelta(days=1)
        start = datetime(day.year, day.month, day.day, 9, tzinfo=zone).astimezone(UTC)
        end = start + timedelta(hours=2)
        connection.execute(
            text("""INSERT INTO organisation_units
(unit_id,name,short_name,category,is_active,valid_from,time_zone,version)
VALUES(:id,'Target RFA','T-RFA','delivery_team',true,:at,'Europe/London',1)"""),
            {"id": target_unit, "at": now},
        )
        connection.execute(
            text("""INSERT INTO organisation_unit_closure VALUES(:id,:id,0)"""), {"id": target_unit}
        )
        connection.execute(
            text("""INSERT INTO identity_account_projection
(user_id,is_active,roles,credential_version,source_hash) VALUES
(:manager,true,ARRAY['Manager'],1,:manager_hash),(:target,true,ARRAY['Analyst'],1,:target_hash)"""),
            {
                "manager": target_manager,
                "target": target_user,
                "manager_hash": "e" * 64,
                "target_hash": "d" * 64,
            },
        )
        connection.execute(
            text("""INSERT INTO team_memberships
(membership_id,user_id,unit_id,role,state,assignment_eligible,valid_from,created_by_user_id,
reason,provenance,version) VALUES(:membership,:target,:unit,'member','active',true,:at,
:manager,'Target posting','test',1)"""),
            {
                "membership": membership,
                "target": target_user,
                "unit": target_unit,
                "at": now,
                "manager": target_manager,
            },
        )
        for grant, manager, unit, action in (
            (source_grant, source_manager, None, "task:transfer"),
            (target_grant, target_manager, target_unit, "task:transfer"),
            (target_assign_grant, target_manager, target_unit, "task:assign"),
        ):
            resolved_unit = (
                unit
                or connection.execute(
                    text("""SELECT unit_id FROM organisation_units
WHERE name='Synthetic RFA Team'""")
                ).scalar_one()
            )
            connection.execute(
                text("""INSERT INTO team_management_grants
(grant_id,manager_user_id,root_unit_id,action,include_descendants,valid_from,created_by_user_id,
reason,version) VALUES(:grant,:manager,:unit,:action,false,:at,:manager,'Test grant',1)"""),
                {
                    "grant": grant,
                    "manager": manager,
                    "unit": resolved_unit,
                    "action": action,
                    "at": now,
                },
            )
        connection.execute(
            text("""INSERT INTO working_patterns
(pattern_id,user_id,time_zone,monday_minutes,tuesday_minutes,wednesday_minutes,thursday_minutes,
friday_minutes,saturday_minutes,sunday_minutes,valid_from,version,provenance,created_at,updated_at)
VALUES(:id,:user,'Europe/London',480,480,480,480,480,480,480,:at,1,'test',:at,:at)"""),
            {"id": uuid4(), "user": target_user, "at": now},
        )
    return start, end


def _upgrade_runtime(database_url: str) -> None:
    _upgrade(database_url)
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
