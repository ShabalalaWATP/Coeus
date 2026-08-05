"""PostgreSQL fixture support for accountable-owner handover tests."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from coeus.domain.enums import TicketState
from coeus.domain.organisation_bootstrap import OrganisationBootstrapPlan
from coeus.domain.tickets import AnalystAssignment, IntakeDetails, RoutingRoute, TicketRecord
from coeus.domain.work_package_handovers import (
    ReservationDisposition,
    ReservationHandover,
    WorkPackageHandoverRequest,
)
from coeus.persistence.organisation_bootstrap_postgres import PostgresOrganisationBootstrapStore
from coeus.persistence.state_store import PostgresStateStore
from coeus.repositories.tickets import InMemoryTicketRepository

API_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class HandoverEvidence:
    actor_id: UUID
    owner_id: UUID
    target_id: UUID
    unit_id: UUID
    package_id: UUID
    predecessor_id: UUID
    reservation_id: UUID
    contributor_id: UUID
    contributor_reservation_id: UUID
    ticket: TicketRecord
    request: WorkPackageHandoverRequest


def upgrade_handover_schema(database_url: str) -> None:
    # Reservation writes now carry the participant role added after 0036, so the
    # handover store needs the whole schema rather than the revision that
    # introduced handovers.
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def _next_work_interval() -> tuple[datetime, datetime]:
    zone = ZoneInfo("Europe/London")
    day = datetime.now(zone).date() + timedelta(days=1)
    while day.weekday() > 4:
        day += timedelta(days=1)
    start = datetime(day.year, day.month, day.day, 9, tzinfo=zone).astimezone(UTC)
    return start, start + timedelta(hours=4)


def insert_handover_evidence(database_url: str, *, target_minutes: int = 480) -> HandoverEvidence:
    engine = create_engine(database_url)
    actor_id, owner_id, target_id, unit_id = uuid4(), uuid4(), uuid4(), uuid4()
    contributor_id = uuid4()
    topology = PostgresOrganisationBootstrapStore(engine).bootstrap(
        OrganisationBootstrapPlan(
            uuid4(), actor_id, unit_id, "Synthetic RFA Team", "SYN-RFA", "Europe/London", ""
        )
    )
    now = datetime.now(UTC)
    ticket = TicketRecord(
        uuid4(),
        "TCK-HANDOVER-0001",
        uuid4(),
        TicketState.ANALYST_IN_PROGRESS,
        IntakeDetails(title="Synthetic handover task"),
    )
    ticket = replace(
        ticket,
        analyst_assignments=(
            AnalystAssignment(
                uuid4(),
                ticket.ticket_id,
                target_id,
                actor_id,
                RoutingRoute.RFA,
                now,
                unit_id,
                "Synthetic RFA Team",
            ),
        ),
    )
    InMemoryTicketRepository(PostgresStateStore(database_url, "relational")).save(ticket)
    package_id, predecessor_id = uuid4(), uuid4()
    membership_id, grant_id, reservation_id = uuid4(), uuid4(), uuid4()
    contributor_reservation_id = uuid4()
    start, end = _next_work_interval()
    with engine.connect() as connection:
        ticket_version, ticket_hash = connection.execute(
            text(
                "SELECT version,canonical_hash FROM coeus_ticket_aggregates WHERE ticket_id=:ticket"
            ),
            {"ticket": ticket.ticket_id},
        ).one()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO identity_account_projection"
                "(user_id,is_active,roles,credential_version,source_hash) VALUES "
                "(:actor,true,ARRAY['Administrator'],2,:actor_hash),"
                "(:target,true,ARRAY['Analyst'],7,:target_hash)"
            ),
            {
                "actor": actor_id,
                "actor_hash": "a" * 64,
                "target": target_id,
                "target_hash": "b" * 64,
            },
        )
        connection.execute(
            text(
                "INSERT INTO team_memberships"
                "(membership_id,user_id,unit_id,role,state,assignment_eligible,valid_from,"
                "created_by_user_id,reason,provenance,version) VALUES "
                "(:membership,:target,:unit,'member','active',true,:now,:actor,"
                "'Synthetic target posting','test',3)"
            ),
            {
                "membership": membership_id,
                "target": target_id,
                "unit": unit_id,
                "actor": actor_id,
                "now": now,
            },
        )
        connection.execute(
            text(
                "INSERT INTO team_management_grants"
                "(grant_id,manager_user_id,root_unit_id,action,include_descendants,valid_from,"
                "created_by_user_id,reason,version) VALUES "
                "(:grant,:actor,:unit,'task:assign',false,:now,:actor,'Synthetic grant',4)"
            ),
            {"grant": grant_id, "actor": actor_id, "unit": unit_id, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO team_task_ownership"
                "(ownership_id,ticket_id,workflow_leg,owning_unit_id,manager_user_id,state,"
                "accepted_at,topology_revision_id,capability_policy_version,version,"
                "history_reference,provenance,reason,created_at) VALUES "
                "(:ownership,:ticket,'rfa',:unit,:actor,'active',:now,:topology,1,2,"
                ":history,'test','Synthetic ownership',:now)"
            ),
            {
                "ownership": uuid4(),
                "ticket": ticket.ticket_id,
                "unit": unit_id,
                "actor": actor_id,
                "now": now,
                "topology": topology.topology_revision_id,
                "history": uuid4(),
            },
        )
        connection.execute(
            text(
                "INSERT INTO canonical_work_packages"
                "(package_id,ticket_id,workflow_leg,owning_unit_id,accountable_user_id,title,"
                "state,estimated_minutes,remaining_minutes,sort_order,version,provenance,"
                "created_at,updated_at) VALUES "
                "(:package,:ticket,'rfa',:unit,:owner,'Synthetic handover','ready',240,240,0,1,"
                "'test',:now,:now),"
                "(:predecessor,:ticket,'rfa',:unit,:owner,'Synthetic predecessor','complete',"
                "120,0,1,1,'test',:now,:now)"
            ),
            {
                "package": package_id,
                "predecessor": predecessor_id,
                "ticket": ticket.ticket_id,
                "unit": unit_id,
                "owner": owner_id,
                "now": now,
            },
        )
        connection.execute(
            text(
                "INSERT INTO work_package_participants"
                "(package_id,user_id,role,active,created_at) VALUES "
                "(:package,:owner,'accountable',true,:now),"
                "(:package,:target,'contributor',true,:now),"
                "(:package,:contributor,'contributor',true,:now)"
            ),
            {
                "package": package_id,
                "owner": owner_id,
                "target": target_id,
                "contributor": contributor_id,
                "now": now,
            },
        )
        connection.execute(
            text(
                "INSERT INTO work_package_dependencies"
                "(package_id,predecessor_package_id,created_by_user_id,created_at) "
                "VALUES (:package,:predecessor,:actor,:now)"
            ),
            {
                "package": package_id,
                "predecessor": predecessor_id,
                "actor": actor_id,
                "now": now,
            },
        )
        connection.execute(
            text(
                "INSERT INTO working_patterns"
                "(pattern_id,user_id,time_zone,monday_minutes,tuesday_minutes,wednesday_minutes,"
                "thursday_minutes,friday_minutes,saturday_minutes,sunday_minutes,valid_from,"
                "version,provenance,created_at,updated_at) VALUES "
                "(:pattern,:target,'Europe/London',:minutes,:minutes,:minutes,:minutes,:minutes,"
                "0,0,:now,1,'test',:now,:now)"
            ),
            {"pattern": uuid4(), "target": target_id, "minutes": target_minutes, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO capacity_reservations"
                "(reservation_id,user_id,ticket_id,workflow_leg,package_id,starts_at,ends_at,"
                "reserved_minutes,state,idempotency_key,request_hash,actor_user_id,version,"
                "created_at,updated_at) VALUES "
                "(:reservation,:owner,:ticket,'rfa',:package,:start,:end,120,'active',"
                "'source-reservation',:hash,:actor,1,:now,:now),"
                "(:contributor_reservation,:contributor,:ticket,'rfa',:package,:start,:end,60,"
                "'active','contributor-reservation',:hash,:actor,1,:now,:now)"
            ),
            {
                "reservation": reservation_id,
                "contributor_reservation": contributor_reservation_id,
                "owner": owner_id,
                "contributor": contributor_id,
                "ticket": ticket.ticket_id,
                "package": package_id,
                "start": start,
                "end": end,
                "hash": "c" * 64,
                "actor": actor_id,
                "now": now,
            },
        )
    engine.dispose()
    request = WorkPackageHandoverRequest(
        unit_id,
        package_id,
        target_id,
        1,
        2,
        grant_id,
        4,
        membership_id,
        3,
        7,
        "b" * 64,
        int(ticket_version),
        str(ticket_hash),
        (
            ReservationHandover(
                reservation_id,
                1,
                ReservationDisposition.REPLACE,
                uuid4(),
                "target-replacement",
            ),
        ),
    )
    return HandoverEvidence(
        actor_id,
        owner_id,
        target_id,
        unit_id,
        package_id,
        predecessor_id,
        reservation_id,
        contributor_id,
        contributor_reservation_id,
        ticket,
        request,
    )
