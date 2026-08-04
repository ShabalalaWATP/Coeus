"""Real PostgreSQL support for deterministic assignment recommendation tests."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import Connection

from coeus.domain.assignment_recommendations import (
    AssignmentDemand,
    AssignmentRecommendationAcceptance,
    AssignmentRecommendationPreview,
    PrepareRecommendationRequest,
)
from coeus.domain.enums import TicketState
from coeus.domain.organisation_bootstrap import OrganisationBootstrapPlan
from coeus.domain.team_task_ownership import AssignmentOwnershipIntent, WorkflowLeg
from coeus.domain.tickets import (
    AnalystAssignment,
    AnalystWorkPackage,
    IntakeDetails,
    RoutingRoute,
    TicketRecord,
    WorkPackageStatus,
)
from coeus.domain.workflow_transaction import WorkflowAuditIntent
from coeus.persistence.assignment_recommendations_postgres import (
    PostgresAssignmentRecommendationStore,
)
from coeus.persistence.organisation_bootstrap_postgres import PostgresOrganisationBootstrapStore
from coeus.persistence.state_store import PostgresStateStore
from coeus.repositories.tickets import InMemoryTicketRepository

API_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class RecommendationEvidence:
    engine: Engine
    actor_id: UUID
    analyst_ids: tuple[UUID, UUID]
    unit_id: UUID
    ticket: TicketRecord
    demand: AssignmentDemand


def recommendation_evidence(database_url: str) -> RecommendationEvidence:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    actor_id, unit_id = uuid4(), uuid4()
    first_analyst, second_analyst = sorted((uuid4(), uuid4()), key=str)
    analysts = (first_analyst, second_analyst)
    topology = PostgresOrganisationBootstrapStore(engine).bootstrap(
        OrganisationBootstrapPlan(
            uuid4(), actor_id, unit_id, "Synthetic Assignment Team", "SAT", "Europe/London", ""
        )
    )
    now = datetime.now(UTC)
    deadline = now + timedelta(days=7)
    ticket = TicketRecord(
        uuid4(),
        "TCK-RECOMMEND-0001",
        uuid4(),
        TicketState.ANALYST_ASSIGNMENT,
        IntakeDetails(title="Synthetic recommendation task"),
    )
    InMemoryTicketRepository(PostgresStateStore(database_url, "relational")).save(ticket)
    with engine.begin() as connection:
        _insert_authority(connection, actor_id, unit_id, topology.topology_revision_id, now)
        for analyst_id in analysts:
            _insert_analyst(connection, actor_id, analyst_id, unit_id, now)
    return RecommendationEvidence(
        engine,
        actor_id,
        analysts,
        unit_id,
        ticket,
        AssignmentDemand(
            ticket.ticket_id,
            WorkflowLeg.RFA,
            120,
            240,
            now,
            deadline,
            ("RFA-SYNTHETIC",),
        ),
    )


def accepted_ticket(
    evidence: RecommendationEvidence, analyst_id: UUID
) -> tuple[TicketRecord, AssignmentOwnershipIntent]:
    now = datetime.now(UTC)
    assignment = AnalystAssignment(
        uuid4(),
        evidence.ticket.ticket_id,
        analyst_id,
        evidence.actor_id,
        RoutingRoute.RFA,
        now,
        evidence.unit_id,
        "Synthetic Assignment Team",
    )
    package = AnalystWorkPackage(
        uuid4(),
        evidence.ticket.ticket_id,
        "Assess the synthetic reporting",
        WorkPackageStatus.PENDING,
        1,
        now,
    )
    updated = replace(
        evidence.ticket,
        state=TicketState.ANALYST_IN_PROGRESS,
        analyst_assignments=(assignment,),
        work_packages=(package,),
    )
    return updated, AssignmentOwnershipIntent(
        evidence.unit_id,
        WorkflowLeg.RFA,
        evidence.actor_id,
        uuid4(),
        evidence.demand.deadline.date(),
    )


def acceptance(
    preview: AssignmentRecommendationPreview,
    actor_id: UUID,
    unit_id: UUID,
    analyst_id: UUID,
    reason: str = "",
) -> AssignmentRecommendationAcceptance:
    return AssignmentRecommendationAcceptance(
        preview.recommendation_id,
        preview.preview_hash,
        actor_id,
        unit_id,
        analyst_id,
        reason,
    )


def prepare(evidence: RecommendationEvidence) -> AssignmentRecommendationPreview:
    return PostgresAssignmentRecommendationStore(evidence.engine).prepare(
        evidence.actor_id, PrepareRecommendationRequest(evidence.demand, evidence.unit_id)
    )


def assignment_audit(evidence: RecommendationEvidence) -> tuple[WorkflowAuditIntent, ...]:
    return (
        WorkflowAuditIntent(
            "analyst_assigned",
            evidence.actor_id,
            {"ticket_id": str(evidence.ticket.ticket_id)},
        ),
    )


def _insert_authority(
    connection: Connection,
    actor_id: UUID,
    unit_id: UUID,
    topology_id: UUID,
    now: datetime,
) -> None:
    profile_id = uuid4()
    connection.execute(
        text(
            "INSERT INTO identity_account_projection(user_id,is_active,roles,credential_version,"
            "source_hash) VALUES (:actor,true,ARRAY['RFA Manager'],1,:hash)"
        ),
        {"actor": actor_id, "hash": "a" * 64},
    )
    connection.execute(
        text(
            "INSERT INTO team_delivery_profiles(profile_id,unit_id,route,wip_limit,weekly_hours,"
            "policy_version,is_active,provenance) VALUES (:profile,:unit,'rfa',4,40,1,true,'test')"
        ),
        {"profile": profile_id, "unit": unit_id},
    )
    connection.execute(
        text(
            "INSERT INTO team_capability_coverage(coverage_id,profile_id,capability_id,proficiency,"
            "valid_from,policy_version,approved_by_user_id) VALUES "
            "(:coverage,:profile,'RFA-SYNTHETIC',3,:now,1,:actor)"
        ),
        {"coverage": uuid4(), "profile": profile_id, "now": now, "actor": actor_id},
    )
    connection.execute(
        text(
            "INSERT INTO team_management_grants(grant_id,manager_user_id,root_unit_id,action,"
            "include_descendants,valid_from,created_by_user_id,reason,version) VALUES "
            "(:grant,:actor,:unit,'task:assign',false,:now,:actor,'Synthetic assignment',1)"
        ),
        {"grant": uuid4(), "actor": actor_id, "unit": unit_id, "now": now},
    )


def _insert_analyst(
    connection: Connection,
    actor_id: UUID,
    analyst_id: UUID,
    unit_id: UUID,
    now: datetime,
) -> None:
    connection.execute(
        text(
            "INSERT INTO identity_account_projection(user_id,is_active,roles,credential_version,"
            "source_hash) VALUES (:user,true,ARRAY['Analyst'],1,:hash)"
        ),
        {"user": analyst_id, "hash": str(analyst_id).replace("-", "") * 2},
    )
    connection.execute(
        text(
            "INSERT INTO team_memberships(membership_id,user_id,unit_id,role,state,"
            "assignment_eligible,valid_from,created_by_user_id,reason,provenance,version) VALUES "
            "(:membership,:user,:unit,'member','active',true,:now,:actor,"
            "'Synthetic posting','test',1)"
        ),
        {"membership": uuid4(), "user": analyst_id, "unit": unit_id, "now": now, "actor": actor_id},
    )
    connection.execute(
        text(
            "INSERT INTO assignment_competencies(competency_id,user_id,capability_id,proficiency,"
            "verified_by_user_id,verified_at,evidence_reference,version,provenance,created_at,"
            "updated_at) VALUES (:competency,:user,'RFA-SYNTHETIC',3,:actor,:now,'synthetic',1,"
            "'test',:now,:now)"
        ),
        {"competency": uuid4(), "user": analyst_id, "actor": actor_id, "now": now},
    )
    connection.execute(
        text(
            "INSERT INTO working_patterns(pattern_id,user_id,time_zone,monday_minutes,"
            "tuesday_minutes,"
            "wednesday_minutes,thursday_minutes,friday_minutes,saturday_minutes,sunday_minutes,"
            "valid_from,version,provenance,created_at,updated_at) VALUES "
            "(:pattern,:user,'Europe/London',480,480,480,480,480,0,0,:now,1,'test',:now,:now)"
        ),
        {"pattern": uuid4(), "user": analyst_id, "now": now},
    )
