"""Serialisable, audited PostgreSQL organisation bootstrap ceremony."""

import json
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_bootstrap import (
    OrganisationBootstrapPlan,
    OrganisationBootstrapResult,
    OrganisationBootstrapUnavailable,
)
from coeus.persistence.serializable_retry import retry_serializable_once

BOOTSTRAP_ACTIONS = tuple(ManagementAction)


class PostgresOrganisationBootstrapStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def bootstrap(self, plan: OrganisationBootstrapPlan) -> OrganisationBootstrapResult:
        return retry_serializable_once(lambda: self._bootstrap_once(plan))

    def _bootstrap_once(self, plan: OrganisationBootstrapPlan) -> OrganisationBootstrapResult:
        denied = False
        result: OrganisationBootstrapResult | None = None
        with self._engine.begin() as connection:
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": "coeus:organisation:bootstrap:v1"},
            )
            if _already_initialised(connection):
                _append_denial(connection, plan)
                denied = True
            else:
                result = _create_foundation(connection, plan)
        if denied:
            raise OrganisationBootstrapUnavailable("organisation bootstrap is permanently closed")
        if result is None:
            raise RuntimeError("organisation bootstrap completed without a result")
        return result


def _already_initialised(connection: Connection) -> bool:
    return bool(
        connection.execute(
            text(
                "SELECT EXISTS(SELECT 1 FROM organisation_bootstrap_state) OR "
                "EXISTS(SELECT 1 FROM organisation_units) OR "
                "EXISTS(SELECT 1 FROM team_management_grants)"
            )
        ).scalar_one()
    )


def _create_foundation(
    connection: Connection, plan: OrganisationBootstrapPlan
) -> OrganisationBootstrapResult:
    occurred_at = _transaction_time(connection)
    revision_id = uuid5(NAMESPACE_URL, f"coeus:organisation:bootstrap:revision:{plan.command_id}")
    connection.execute(
        text(_INSERT_ROOT),
        {
            "unit_id": plan.root_unit_id,
            "name": plan.root_name,
            "short_name": plan.root_short_name,
            "category": plan.category.value,
            "valid_from": occurred_at,
            "time_zone": plan.time_zone,
            "description": plan.description,
        },
    ).one()
    connection.execute(
        text(
            "INSERT INTO organisation_unit_closure"
            "(ancestor_unit_id,descendant_unit_id,depth) VALUES (:unit_id,:unit_id,0)"
        ),
        {"unit_id": plan.root_unit_id},
    )
    connection.execute(
        text(_INSERT_REVISION),
        {
            "revision_id": revision_id,
            "unit_id": plan.root_unit_id,
            "path": [plan.root_unit_id],
            "valid_from": occurred_at,
            "command_id": plan.command_id,
            "actor_id": plan.actor_user_id,
        },
    ).one()
    grant_ids = tuple(
        _insert_grant(connection, plan, action, occurred_at) for action in BOOTSTRAP_ACTIONS
    )
    connection.execute(
        text(
            "INSERT INTO organisation_bootstrap_state"
            "(singleton,ceremony_id,completed_by_user_id,completed_at,root_unit_id) "
            "VALUES (true,:command_id,:actor_id,:occurred_at,:root_unit_id) "
            "RETURNING ceremony_id"
        ),
        {
            "command_id": plan.command_id,
            "actor_id": plan.actor_user_id,
            "occurred_at": occurred_at,
            "root_unit_id": plan.root_unit_id,
        },
    ).one()
    connection.execute(
        text(
            "INSERT INTO effective_authority_epochs"
            "(principal_id,scope_unit_id,epoch,advanced_at) VALUES "
            "(:actor_id,:root_unit_id,1,:occurred_at)"
        ),
        {
            "actor_id": plan.actor_user_id,
            "root_unit_id": plan.root_unit_id,
            "occurred_at": occurred_at,
        },
    )
    _append_success(connection, plan, occurred_at, len(grant_ids))
    return OrganisationBootstrapResult(plan.root_unit_id, revision_id, grant_ids)


def _insert_grant(
    connection: Connection,
    plan: OrganisationBootstrapPlan,
    action: ManagementAction,
    occurred_at: datetime,
) -> UUID:
    grant_id = uuid5(
        NAMESPACE_URL, f"coeus:organisation:bootstrap:grant:{plan.command_id}:{action.value}"
    )
    connection.execute(
        text(_INSERT_GRANT),
        {
            "grant_id": grant_id,
            "actor_id": plan.actor_user_id,
            "root_unit_id": plan.root_unit_id,
            "action": action.value,
            "occurred_at": occurred_at,
        },
    ).one()
    return grant_id


def _transaction_time(connection: Connection) -> datetime:
    value = connection.execute(text("SELECT transaction_timestamp()")).scalar_one()
    if not isinstance(value, datetime):
        raise RuntimeError("PostgreSQL did not return a transaction timestamp")
    return value


def _append_success(
    connection: Connection,
    plan: OrganisationBootstrapPlan,
    occurred_at: datetime,
    grant_count: int,
) -> None:
    payload = json.dumps(
        {"root_unit_id": str(plan.root_unit_id), "grant_count": grant_count}, sort_keys=True
    )
    _append_evidence(
        connection,
        plan,
        "organisation_bootstrapped",
        occurred_at,
        payload,
        include_outbox=True,
    )


def _append_denial(connection: Connection, plan: OrganisationBootstrapPlan) -> None:
    _append_evidence(
        connection,
        plan,
        "organisation_bootstrap_denied",
        _transaction_time(connection),
        json.dumps({"reason": "already_initialised"}),
        include_outbox=False,
    )


def _append_evidence(
    connection: Connection,
    plan: OrganisationBootstrapPlan,
    event_type: str,
    occurred_at: datetime,
    payload: str,
    *,
    include_outbox: bool,
) -> None:
    event_id = uuid5(NAMESPACE_URL, f"coeus:organisation:{event_type}:{plan.command_id}")
    values = {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": occurred_at,
        "actor_id": str(plan.actor_user_id),
        "payload": payload,
    }
    connection.execute(text(_INSERT_AUDIT), values)
    if include_outbox:
        connection.execute(text(_INSERT_OUTBOX), values)


_INSERT_ROOT = """
INSERT INTO organisation_units(unit_id,name,short_name,category,parent_unit_id,is_active,
 valid_from,valid_until,time_zone,description,provenance,version)
VALUES (:unit_id,:name,:short_name,:category,NULL,true,:valid_from,NULL,:time_zone,
 :description,'bootstrap',1) RETURNING unit_id
"""

_INSERT_REVISION = """
INSERT INTO organisation_topology_revisions(revision_id,unit_id,parent_unit_id,path,valid_from,
 valid_until,change_command_id,changed_by_user_id)
VALUES (:revision_id,:unit_id,NULL,:path,:valid_from,NULL,:command_id,:actor_id)
RETURNING revision_id
"""

_INSERT_GRANT = """
INSERT INTO team_management_grants(grant_id,manager_user_id,root_unit_id,action,
 include_descendants,valid_from,valid_until,revoked_at,created_by_user_id,reason,
 source_grant_id,delegation_depth,version)
VALUES (:grant_id,:actor_id,:root_unit_id,:action,true,:occurred_at,NULL,NULL,:actor_id,
 'Initial organisation bootstrap authority.',NULL,0,1) RETURNING grant_id
"""

_INSERT_AUDIT = """
INSERT INTO coeus_audit_events(event_id,event_type,occurred_at,actor_user_id,metadata)
VALUES (:event_id,:event_type,:occurred_at,:actor_id,CAST(:payload AS jsonb))
ON CONFLICT (event_id) DO NOTHING
"""

_INSERT_OUTBOX = """
INSERT INTO coeus_outbox(event_id,aggregate_id,aggregate_version,event_type,payload)
VALUES (:event_id,:event_id,1,:event_type,CAST(:payload AS jsonb))
ON CONFLICT (aggregate_id,aggregate_version,event_type) DO NOTHING
"""
