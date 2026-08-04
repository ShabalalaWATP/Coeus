"""Synthetic rows proving recovery for migrations 0041 through 0045."""

from uuid import UUID, uuid4

from backup_restore_cutover_support import seed_cutover_recovery_rows
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from coeus.persistence.postgres_backup_tables import TABLES

DEDUPLICATION_KEY = "synthetic-provider:recovery-event"
FOLLOW_ON_TABLES = frozenset(
    {
        "calendar_commitment_notifications",
        "calendar_commitment_responses",
        "capacity_reservations",
        "package_lifecycle_conflicts",
        "predecessor_cancellation_commands",
        "team_workspace_policies",
        "workspace_export_jobs",
        "workspace_store_links",
    }
)
CUTOVER_TABLES = frozenset(
    {
        "organisation_cutover_approvals",
        "organisation_cutover_checkpoint_events",
        "organisation_cutover_checkpoints",
        "organisation_cutover_evidence",
        "organisation_cutover_manifests",
        "organisation_cutover_recovery_events",
        "organisation_cutover_release",
        "organisation_cutover_slice_state",
        "organisation_cutover_writer_fences",
    }
)
FIXTURE_TABLES = (
    frozenset(
        [
            "assignment_competencies",
            "calendar_events",
            "canonical_work_packages",
            "organisation_units",
            "team_management_grants",
            "team_memberships",
            "work_package_dependencies",
            "work_package_participants",
            "working_patterns",
        ]
    )
    | FOLLOW_ON_TABLES
    | CUTOVER_TABLES
)
SPRINT_24_PREFIXES = tuple(
    [
        "assignment_",
        "calendar_",
        "canonical_",
        "capacity_",
        "effective_",
        "identity_account_",
        "organisation_",
        "package_",
        "predecessor_",
        "synthetic_",
        "team_",
        "work_package_",
        "workflow_",
        "working_",
        "workspace_",
    ]
)
SPRINT_24_TABLES = {spec.name for spec in TABLES if spec.name.startswith(SPRINT_24_PREFIXES)}


def seed_follow_on_recovery_rows(connection: Connection, actor_id: UUID) -> UUID:
    event = connection.execute(
        text("SELECT event_id,owner_user_id FROM calendar_events ORDER BY event_id LIMIT 1")
    ).one()
    connection.execute(
        text("UPDATE calendar_events SET deduplication_key=:key WHERE event_id=:event_id"),
        {"event_id": event.event_id, "key": DEDUPLICATION_KEY},
    )
    connection.execute(
        text(
            "INSERT INTO calendar_commitment_responses"
            "(event_id,subject_user_id,response_state,response_version,responded_at,updated_at) "
            "VALUES (:event_id,:subject,'acknowledged',2,now(),now())"
        ),
        {"event_id": event.event_id, "subject": event.owner_user_id},
    )
    connection.execute(
        text(
            "INSERT INTO calendar_commitment_notifications"
            "(notification_id,event_id,recipient_user_id,notification_type,created_at) "
            "VALUES (:notification,:event_id,:recipient,'acknowledged',now())"
        ),
        {
            "notification": uuid4(),
            "event_id": event.event_id,
            "recipient": event.owner_user_id,
        },
    )
    package = connection.execute(text(_PACKAGE)).one()
    connection.execute(
        text(_RESERVATION),
        {
            "reservation": uuid4(),
            "user_id": package.user_id,
            "ticket_id": package.ticket_id,
            "workflow_leg": package.workflow_leg,
            "package_id": package.package_id,
            "key": f"recovery-{uuid4()}",
            "request_hash": "c" * 64,
            "actor": actor_id,
            "role": package.role,
        },
    )
    connection.execute(
        text(_CONFLICT),
        {"conflict": uuid4(), "package_id": package.package_id},
    )
    connection.execute(
        text(_CANCELLATION),
        {
            "command": uuid4(),
            "actor": actor_id,
            "key": f"recovery-{uuid4()}",
            "package_id": package.package_id,
            "version": package.version,
        },
    )
    connection.execute(
        text(_STORE_LINK),
        {
            "link": uuid4(),
            "actor": actor_id,
            "unit_id": package.owning_unit_id,
            "package_id": package.package_id,
            "target": uuid4(),
        },
    )
    grant = connection.execute(
        text(
            "SELECT grant_id,root_unit_id AS unit_id,version "
            "FROM team_management_grants ORDER BY grant_id LIMIT 1"
        )
    ).one()
    connection.execute(
        text(_WORKSPACE_POLICY),
        {"unit_id": grant.unit_id, "actor": actor_id},
    )
    connection.execute(
        text(_EXPORT_JOB),
        {
            "export_id": uuid4(),
            "actor": actor_id,
            "unit_id": grant.unit_id,
            "grant_id": grant.grant_id,
            "grant_version": grant.version,
            "command_id": uuid4(),
            "key": f"recovery-{uuid4()}",
        },
    )
    seed_cutover_recovery_rows(connection, actor_id)
    return UUID(str(event.event_id))


def restored_deduplication_key(database_url: str) -> str | None:
    with create_engine(database_url).connect() as connection:
        value = connection.execute(
            text(
                "SELECT deduplication_key FROM calendar_events WHERE deduplication_key IS NOT NULL"
            )
        ).scalar_one_or_none()
    return None if value is None else str(value)


_PACKAGE = """
SELECT participant.user_id,participant.role,package.package_id,package.ticket_id,
       package.workflow_leg,package.owning_unit_id,package.version
FROM work_package_participants participant
JOIN canonical_work_packages package ON package.package_id=participant.package_id
WHERE participant.active ORDER BY package.package_id,participant.user_id LIMIT 1
"""

_RESERVATION = """
INSERT INTO capacity_reservations(
 reservation_id,user_id,ticket_id,workflow_leg,package_id,starts_at,ends_at,
 reserved_minutes,state,expires_at,idempotency_key,request_hash,actor_user_id,
 version,created_at,updated_at,participant_role)
VALUES (:reservation,:user_id,:ticket_id,:workflow_leg,:package_id,
 now()+interval '1 day',now()+interval '1 day 1 hour',60,'active',NULL,:key,
 :request_hash,:actor,1,now(),now(),:role)
"""

_CONFLICT = """
INSERT INTO package_lifecycle_conflicts(
 conflict_id,package_id,reason_code,source_type,source_id,status,evidence,observed_at)
VALUES (:conflict,:package_id,'synthetic_recovery','package',:package_id,'open','{}',now())
"""

_CANCELLATION = """
INSERT INTO predecessor_cancellation_commands(
 command_id,actor_user_id,idempotency_key,request_hash,package_id,
 expected_package_version,result_package_version,dispositions,occurred_at)
VALUES (:command,:actor,:key,'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd',
 :package_id,:version,:version,'{}',now())
"""

_STORE_LINK = """
INSERT INTO workspace_store_links(
 link_id,owner_user_id,unit_id,source_type,source_id,target_type,target_id,label,
 version,created_at,updated_at)
VALUES (:link,:actor,:unit_id,'work_package',:package_id,'project',:target,
 'Synthetic recovery link',1,now(),now())
"""

_WORKSPACE_POLICY = """
INSERT INTO team_workspace_policies(
 unit_id,service_target_hours,planning_cadence,planning_weekday,planning_local_time,
 planning_duration_minutes,version,updated_by_user_id,updated_at)
VALUES (:unit_id,48,'weekly',1,'09:00',60,1,:actor,now())
"""

_EXPORT_JOB = """
INSERT INTO workspace_export_jobs(
 export_id,actor_user_id,unit_id,include_descendants,authorising_grant_id,
 authorising_grant_version,command_id,idempotency_key,request_hash,state,row_count,
 snapshot_payload,handling_marking,created_at,expires_at)
VALUES (:export_id,:actor,:unit_id,true,:grant_id,:grant_version,:command_id,:key,
 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee','ready',1,
 '{"rows":[]}'::jsonb,'OFFICIAL-SENSITIVE',now(),now()+interval '1 hour')
"""
