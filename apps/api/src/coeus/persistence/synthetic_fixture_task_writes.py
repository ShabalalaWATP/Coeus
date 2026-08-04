"""Atomic inserts for conflict-free synthetic tasks and work packages."""

import json
from datetime import timedelta
from hashlib import sha256
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.synthetic_organisation_fixture import SyntheticFixtureUser
from coeus.persistence.state_store import _shadow_ticket_payload
from coeus.persistence.synthetic_fixture_plan import SyntheticFixturePlan
from coeus.persistence.synthetic_fixture_values import PROVENANCE, topology_revision_id
from coeus.repositories.synthetic_organisation_manifest import BASELINE, SyntheticUnitSpec
from coeus.repositories.synthetic_task_manifest import SyntheticTaskSpec
from coeus.repositories.synthetic_task_values import encoded_ticket, package_values


def insert_tasks(
    connection: Connection,
    plan: SyntheticFixturePlan,
    users: dict[str, SyntheticFixtureUser],
    units: dict[str, SyntheticUnitSpec],
) -> None:
    user_ids = {key: value.user_id for key, value in users.items()}
    unit_ids = {key: value.unit_id for key, value in units.items()}
    payloads = [json.loads(encoded_ticket(spec, user_ids, unit_ids).payload) for spec in plan.tasks]
    # Use the runtime ticket writer so aggregate hashing, capacity state,
    # audience projection and outbox behaviour cannot drift in local fixtures.
    _shadow_ticket_payload(connection, {"tickets": payloads}, reconcile=False)
    for spec in plan.task_ownership:
        _insert_ownership(connection, spec, users, units)
    for spec, order in plan.work_packages:
        _insert_package(connection, spec, order, users, units)


def _insert_ownership(
    connection: Connection,
    spec: SyntheticTaskSpec,
    users: dict[str, SyntheticFixtureUser],
    units: dict[str, SyntheticUnitSpec],
) -> None:
    accepted = spec.ownership_state.value in {"accepted", "active", "completed"}
    connection.execute(
        text(
            "INSERT INTO team_task_ownership"
            "(ownership_id,ticket_id,workflow_leg,owning_unit_id,manager_user_id,state,"
            "accepted_at,target_date,topology_revision_id,capability_policy_version,version,"
            "history_reference,provenance,reason,created_at,updated_at) VALUES "
            "(:ownership_id,:ticket_id,:leg,:unit_id,:manager_id,:state,:accepted_at,"
            ":target_date,:revision_id,1,1,:history_reference,:provenance,:reason,"
            ":created_at,:updated_at)"
        ),
        {
            "ownership_id": spec.ownership_id,
            "ticket_id": spec.ticket_id,
            "leg": spec.workflow_leg.value,
            "unit_id": units[spec.unit_key].unit_id,
            "manager_id": users[spec.manager_username].user_id,
            "state": spec.ownership_state.value,
            "accepted_at": BASELINE - timedelta(days=6) if accepted else None,
            "target_date": spec.target_date,
            "revision_id": topology_revision_id(units[spec.unit_key].unit_id),
            "history_reference": spec.history_reference,
            "provenance": PROVENANCE,
            "reason": "Synthetic exercise workload.",
            "created_at": BASELINE - timedelta(days=7),
            "updated_at": BASELINE,
        },
    )


def _insert_package(
    connection: Connection,
    spec: SyntheticTaskSpec,
    order: int,
    users: dict[str, SyntheticFixtureUser],
    units: dict[str, SyntheticUnitSpec],
) -> None:
    values = package_values(spec, order)
    username = values.pop("accountable_username")
    owner_id = users[str(username)].user_id if username else None
    package_id = spec.package_id(order)
    params = {
        "package_id": package_id,
        "ticket_id": spec.ticket_id,
        "leg": spec.workflow_leg.value,
        "unit_id": units[spec.unit_key].unit_id,
        "owner_id": owner_id,
        "sort_order": order,
        "provenance": PROVENANCE,
        "created_at": BASELINE - timedelta(days=6),
        "updated_at": BASELINE,
        **values,
    }
    connection.execute(text(_INSERT_PACKAGE), params)
    if owner_id is not None:
        connection.execute(
            text(
                "INSERT INTO work_package_participants"
                "(package_id,user_id,role,active,created_at,ended_at) "
                "VALUES (:package_id,:user_id,'accountable',true,:created_at,NULL)"
            ),
            {"package_id": package_id, "user_id": owner_id, "created_at": BASELINE},
        )
    if order == 2:
        connection.execute(
            text(
                "INSERT INTO work_package_dependencies"
                "(package_id,predecessor_package_id,created_by_user_id,created_at) "
                "VALUES (:package_id,:predecessor,:actor_id,:created_at)"
            ),
            {
                "package_id": package_id,
                "predecessor": spec.package_id(1),
                "actor_id": users[spec.manager_username].user_id,
                "created_at": BASELINE,
            },
        )
    _insert_package_evidence(connection, spec, order, users[spec.manager_username].user_id)


def _insert_package_evidence(
    connection: Connection, spec: SyntheticTaskSpec, order: int, actor_id: UUID
) -> None:
    evidence = json.dumps({"fixture": True, "task_reference": spec.reference, "order": order})
    request_hash = sha256(evidence.encode()).hexdigest()
    connection.execute(
        text(
            "INSERT INTO work_package_history"
            "(history_id,package_id,version,actor_user_id,event_type,evidence,occurred_at) "
            "VALUES (:history_id,:package_id,1,:actor_id,'synthetic_fixture_created',"
            "CAST(:evidence AS jsonb),:occurred_at)"
        ),
        {
            "history_id": spec.package_history_id(order),
            "package_id": spec.package_id(order),
            "actor_id": actor_id,
            "evidence": evidence,
            "occurred_at": BASELINE,
        },
    )
    connection.execute(
        text(
            "INSERT INTO work_package_commands"
            "(command_id,idempotency_key,request_hash,package_id,actor_user_id,"
            "expected_version,result_version,operation,occurred_at) VALUES "
            "(:command_id,:key,:request_hash,:package_id,:actor_id,0,1,'create',:occurred_at)"
        ),
        {
            "command_id": spec.package_command_id(order),
            "key": f"synthetic-fixture:{spec.key}:package:{order}",
            "request_hash": request_hash,
            "package_id": spec.package_id(order),
            "actor_id": actor_id,
            "occurred_at": BASELINE,
        },
    )


_INSERT_PACKAGE = """
INSERT INTO canonical_work_packages(
 package_id,ticket_id,workflow_leg,owning_unit_id,accountable_user_id,title,state,
 estimated_minutes,remaining_minutes,due_at,priority,priority_override_reason,
 blocked_code,blocked_note,review_at,sort_order,version,provenance,created_at,updated_at)
VALUES (
 :package_id,:ticket_id,:leg,:unit_id,:owner_id,:title,:state,
 :estimated_minutes,:remaining_minutes,:due_at,:priority,'',
 :blocked_code,:blocked_note,:review_at,:sort_order,1,:provenance,:created_at,:updated_at)
"""
