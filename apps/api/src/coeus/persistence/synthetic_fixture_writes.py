"""Atomic writes for an already conflict-free synthetic fixture plan."""

import json
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.synthetic_organisation_fixture import SyntheticFixtureUser
from coeus.persistence.synthetic_fixture_calendar_writes import insert_calendar_events
from coeus.persistence.synthetic_fixture_capacity import insert_capacity_reservations
from coeus.persistence.synthetic_fixture_plan import SyntheticFixturePlan
from coeus.persistence.synthetic_fixture_service_grant_writes import insert_service_grants
from coeus.persistence.synthetic_fixture_task_writes import insert_tasks
from coeus.persistence.synthetic_fixture_values import (
    MEMBERSHIP_REASON,
    PROVENANCE,
    TIME_ZONE,
    UNIT_DESCRIPTION,
    bootstrap_ceremony_id,
    delivery_profile_id,
    fixture_grant_id,
    topology_command_id,
    topology_revision_id,
)
from coeus.repositories.synthetic_organisation_manifest import (
    BASELINE,
    SyntheticUnitSpec,
    SyntheticWorkingPatternSpec,
    synthetic_unit_specs,
)


def apply_fixture_plan(
    connection: Connection,
    plan: SyntheticFixturePlan,
    actor_user_id: UUID,
    users: tuple[SyntheticFixtureUser, ...],
    occurred_at: datetime,
) -> None:
    user_map = {user.username.casefold(): user for user in users}
    units = {item.key: item for item in synthetic_unit_specs()}
    for unit_spec in plan.units:
        _insert_unit(connection, unit_spec, units, actor_user_id, occurred_at)
    for profile_spec in plan.profiles:
        connection.execute(
            text(
                "INSERT INTO team_delivery_profiles"
                "(profile_id,unit_id,route,wip_limit,weekly_hours,policy_version,"
                "is_active,provenance,created_at,updated_at) VALUES "
                "(:profile_id,:unit_id,:route,:wip_limit,40,1,true,:provenance,"
                ":occurred_at,:occurred_at)"
            ),
            {
                "profile_id": delivery_profile_id(profile_spec.unit_id),
                "unit_id": profile_spec.unit_id,
                "route": profile_spec.route.value if profile_spec.route else None,
                "wip_limit": profile_spec.wip_limit,
                "provenance": PROVENANCE,
                "occurred_at": occurred_at,
            },
        )
    for posting_spec in plan.memberships:
        user = user_map[posting_spec.username.casefold()]
        connection.execute(
            text(
                "INSERT INTO team_memberships"
                "(membership_id,user_id,unit_id,role,state,assignment_eligible,"
                "valid_from,valid_until,created_by_user_id,reason,provenance,version,"
                "created_at,updated_at) VALUES "
                "(:membership_id,:user_id,:unit_id,:role,:state,:assignment_eligible,"
                ":valid_from,:valid_until,:actor_id,:reason,:provenance,1,"
                ":occurred_at,:occurred_at)"
            ),
            {
                "membership_id": posting_spec.membership_id,
                "user_id": user.user_id,
                "unit_id": units[posting_spec.unit_key].unit_id,
                "role": posting_spec.role.value,
                "state": posting_spec.state.value,
                "assignment_eligible": posting_spec.assignment_eligible,
                "valid_from": posting_spec.valid_from,
                "valid_until": posting_spec.valid_until,
                "actor_id": actor_user_id,
                "reason": MEMBERSHIP_REASON,
                "provenance": PROVENANCE,
                "occurred_at": occurred_at,
            },
        )
    for pattern_spec in plan.patterns:
        _insert_pattern(
            connection,
            pattern_spec,
            user_map[pattern_spec.username.casefold()].user_id,
            occurred_at,
        )
    for action in plan.grants:
        connection.execute(
            text(
                "INSERT INTO team_management_grants"
                "(grant_id,manager_user_id,root_unit_id,action,include_descendants,"
                "valid_from,valid_until,revoked_at,created_by_user_id,reason,"
                "source_grant_id,delegation_depth,version,created_at,updated_at) VALUES "
                "(:grant_id,:actor_id,:root_id,:action,true,:occurred_at,NULL,NULL,"
                ":actor_id,:reason,NULL,0,1,:occurred_at,:occurred_at)"
            ),
            {
                "grant_id": fixture_grant_id(action),
                "actor_id": actor_user_id,
                "root_id": units["di"].unit_id,
                "action": action.value,
                "reason": "Initial synthetic fixture authority.",
                "occurred_at": occurred_at,
            },
        )
    for grant in plan.management_grants:
        connection.execute(
            text(
                "INSERT INTO team_management_grants"
                "(grant_id,manager_user_id,root_unit_id,action,include_descendants,"
                "valid_from,valid_until,revoked_at,created_by_user_id,reason,"
                "source_grant_id,delegation_depth,version,created_at,updated_at) VALUES "
                "(:grant_id,:manager_id,:root_id,:action,:include_descendants,"
                ":valid_from,NULL,NULL,:actor_id,:reason,NULL,0,1,"
                ":occurred_at,:occurred_at)"
            ),
            {
                "grant_id": grant.grant_id,
                "manager_id": user_map[grant.username.casefold()].user_id,
                "root_id": units[grant.unit_key].unit_id,
                "action": grant.action.value,
                "include_descendants": grant.include_descendants,
                "valid_from": BASELINE,
                "actor_id": actor_user_id,
                "reason": "Synthetic exercise management authority.",
                "occurred_at": occurred_at,
            },
        )
    insert_service_grants(connection, plan, units, actor_user_id, occurred_at)
    for capability in plan.team_capabilities:
        unit = units[capability.unit_key]
        connection.execute(
            text(
                "INSERT INTO team_capability_coverage"
                "(coverage_id,profile_id,capability_id,proficiency,valid_from,"
                "valid_until,policy_version,approved_by_user_id,created_at) VALUES "
                "(:coverage_id,:profile_id,:capability_id,:proficiency,:valid_from,"
                "NULL,1,:actor_id,:occurred_at)"
            ),
            {
                "coverage_id": capability.coverage_id,
                "profile_id": delivery_profile_id(unit.unit_id),
                "capability_id": capability.capability_id,
                "proficiency": capability.proficiency,
                "valid_from": BASELINE,
                "actor_id": actor_user_id,
                "occurred_at": occurred_at,
            },
        )
    for competency in plan.competencies:
        connection.execute(
            text(
                "INSERT INTO assignment_competencies"
                "(competency_id,user_id,capability_id,proficiency,verified_by_user_id,"
                "verified_at,expires_at,evidence_reference,version,provenance,"
                "created_at,updated_at) VALUES (:competency_id,:user_id,:capability_id,"
                ":proficiency,:actor_id,:verified_at,NULL,:evidence,1,:provenance,"
                ":occurred_at,:occurred_at)"
            ),
            {
                "competency_id": competency.competency_id,
                "user_id": user_map[competency.username.casefold()].user_id,
                "capability_id": competency.capability_id,
                "proficiency": competency.proficiency,
                "actor_id": actor_user_id,
                "verified_at": BASELINE,
                "evidence": "synthetic-exercise-fixture",
                "provenance": PROVENANCE,
                "occurred_at": occurred_at,
            },
        )
    insert_calendar_events(
        connection,
        plan.calendar_events,
        user_map,
        units,
        occurred_at,
    )
    insert_tasks(connection, plan, user_map, units)
    insert_capacity_reservations(connection, plan.capacity_reservations, user_map)
    if plan.create_bootstrap_marker:
        connection.execute(
            text(
                "INSERT INTO organisation_bootstrap_state"
                "(singleton,ceremony_id,completed_by_user_id,completed_at,root_unit_id) "
                "VALUES (true,:ceremony_id,:actor_id,:occurred_at,:root_id)"
            ),
            {
                "ceremony_id": bootstrap_ceremony_id(),
                "actor_id": actor_user_id,
                "occurred_at": occurred_at,
                "root_id": units["di"].unit_id,
            },
        )


def append_fixture_evidence(
    connection: Connection,
    command_id: UUID,
    actor_user_id: UUID,
    root_unit_id: UUID,
    occurred_at: datetime,
    payload: dict[str, object],
) -> None:
    event_id = uuid5(NAMESPACE_URL, f"coeus:synthetic-fixture-applied:{command_id}")
    encoded = json.dumps(payload, sort_keys=True)
    connection.execute(
        text(
            "INSERT INTO coeus_audit_events"
            "(event_id,event_type,occurred_at,actor_user_id,metadata) VALUES "
            "(:event_id,'synthetic_organisation_fixture_applied',:occurred_at,"
            ":actor_id,CAST(:payload AS jsonb)) ON CONFLICT (event_id) DO NOTHING"
        ),
        {
            "event_id": event_id,
            "occurred_at": occurred_at,
            "actor_id": str(actor_user_id),
            "payload": encoded,
        },
    )
    connection.execute(
        text(
            "INSERT INTO coeus_outbox"
            "(event_id,aggregate_id,aggregate_version,event_type,payload) VALUES "
            "(:event_id,:root_id,1,'synthetic_organisation_fixture_applied',"
            "CAST(:payload AS jsonb)) ON CONFLICT "
            "(aggregate_id,aggregate_version,event_type) DO NOTHING"
        ),
        {"event_id": event_id, "root_id": root_unit_id, "payload": encoded},
    )


def _insert_unit(
    connection: Connection,
    spec: SyntheticUnitSpec,
    units: dict[str, SyntheticUnitSpec],
    actor_user_id: UUID,
    occurred_at: datetime,
) -> None:
    parent_key = spec.parent_key
    parent_id = units[parent_key].unit_id if parent_key else None
    params: dict[str, object] = {
        "unit_id": spec.unit_id,
        "name": spec.name,
        "short_name": spec.short_name,
        "category": spec.category.value,
        "parent_id": parent_id,
        "valid_from": BASELINE,
        "time_zone": TIME_ZONE,
        "description": UNIT_DESCRIPTION,
        "provenance": PROVENANCE,
        "actor_id": actor_user_id,
    }
    connection.execute(
        text(
            "INSERT INTO organisation_units"
            "(unit_id,name,short_name,category,parent_unit_id,is_active,valid_from,"
            "valid_until,time_zone,description,provenance,version) VALUES "
            "(:unit_id,:name,:short_name,:category,:parent_id,true,:valid_from,NULL,"
            ":time_zone,:description,:provenance,1)"
        ),
        params,
    )
    connection.execute(
        text(
            "INSERT INTO organisation_unit_closure"
            "(ancestor_unit_id,descendant_unit_id,depth) "
            "SELECT ancestor_unit_id,:unit_id,depth+1 FROM organisation_unit_closure "
            "WHERE descendant_unit_id=:parent_id "
            "UNION ALL SELECT :unit_id,:unit_id,0"
        ),
        params,
    )
    params.update(
        revision_id=topology_revision_id(spec.unit_id),
        command_id=topology_command_id(spec.unit_id),
    )
    connection.execute(
        text(
            "INSERT INTO organisation_topology_revisions"
            "(revision_id,unit_id,parent_unit_id,path,valid_from,valid_until,"
            "change_command_id,changed_by_user_id) SELECT :revision_id,:unit_id,"
            ":parent_id,array_agg(ancestor_unit_id ORDER BY depth DESC),:valid_from,"
            "NULL,:command_id,:actor_id FROM organisation_unit_closure "
            "WHERE descendant_unit_id=:unit_id"
        ),
        params,
    )


def _insert_pattern(
    connection: Connection,
    spec: SyntheticWorkingPatternSpec,
    user_id: UUID,
    occurred_at: datetime,
) -> None:
    minutes = spec.weekday_minutes
    connection.execute(
        text(
            "INSERT INTO working_patterns"
            "(pattern_id,user_id,time_zone,monday_minutes,tuesday_minutes,"
            "wednesday_minutes,thursday_minutes,friday_minutes,saturday_minutes,"
            "sunday_minutes,valid_from,valid_until,version,provenance,created_at,updated_at) "
            "VALUES (:pattern_id,:user_id,:time_zone,:minutes,:minutes,:minutes,"
            ":minutes,:minutes,0,0,:valid_from,NULL,1,:provenance,:occurred_at,:occurred_at)"
        ),
        {
            "pattern_id": spec.pattern_id,
            "user_id": user_id,
            "time_zone": TIME_ZONE,
            "minutes": minutes,
            "valid_from": spec.valid_from,
            "provenance": PROVENANCE,
            "occurred_at": occurred_at,
        },
    )
