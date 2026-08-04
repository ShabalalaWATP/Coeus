"""Authority invalidation and append-only evidence for reparent commands."""

import json
from datetime import datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.organisation_reparent import (
    OrganisationReparentCommand,
    OrganisationReparentImpact,
    OrganisationReparentResult,
)


def advance_epochs(
    connection: Connection,
    command: OrganisationReparentCommand,
    impact: OrganisationReparentImpact,
    occurred_at: datetime,
) -> None:
    connection.execute(
        text(
            "INSERT INTO effective_authority_epochs(principal_id,scope_unit_id,epoch,advanced_at) "
            "SELECT DISTINCT manager_user_id,root_unit_id,1,:occurred_at "
            "FROM team_management_grants WHERE root_unit_id IN ("
            "SELECT ancestor_unit_id FROM organisation_unit_closure "
            "WHERE descendant_unit_id=:new_parent_unit_id UNION SELECT descendant_unit_id "
            "FROM organisation_unit_closure WHERE ancestor_unit_id=:unit_id UNION "
            "SELECT unnest(path) FROM organisation_topology_revisions "
            "WHERE revision_id=:source_topology_revision_id) "
            "ON CONFLICT (principal_id,scope_unit_id) DO UPDATE SET "
            "epoch=effective_authority_epochs.epoch + 1,advanced_at=EXCLUDED.advanced_at"
        ),
        {
            **vars(command.request),
            "source_topology_revision_id": impact.source_topology_revision_id,
            "occurred_at": occurred_at,
        },
    )


def append_evidence(
    connection: Connection,
    command: OrganisationReparentCommand,
    impact: OrganisationReparentImpact,
    result: OrganisationReparentResult,
    occurred_at: datetime,
) -> None:
    event_id = uuid5(NAMESPACE_URL, f"coeus:organisation:reparented:{command.command_id}")
    payload = json.dumps(
        {
            "unit_id": str(result.unit_id),
            "source_parent_unit_id": str(impact.source_parent_unit_id),
            "new_parent_unit_id": str(result.parent_unit_id),
            "version": result.version,
            "reason_hash": sha256(command.request.reason.encode()).hexdigest(),
        },
        sort_keys=True,
    )
    values = {
        "event_id": event_id,
        "event_type": "organisation_unit_reparented",
        "occurred_at": occurred_at,
        "actor_user_id": str(command.actor_user_id),
        "unit_id": result.unit_id,
        "result_version": result.version,
        "payload": payload,
    }
    connection.execute(text(_INSERT_AUDIT), values)
    connection.execute(text(_INSERT_OUTBOX), values)


_INSERT_AUDIT = """
INSERT INTO coeus_audit_events(event_id,event_type,occurred_at,actor_user_id,metadata)
VALUES (:event_id,:event_type,:occurred_at,:actor_user_id,CAST(:payload AS jsonb))
ON CONFLICT (event_id) DO NOTHING
"""

_INSERT_OUTBOX = """
INSERT INTO coeus_outbox(event_id,aggregate_id,aggregate_version,event_type,payload)
VALUES (:event_id,:unit_id,:result_version,:event_type,CAST(:payload AS jsonb))
ON CONFLICT (aggregate_id,aggregate_version,event_type) DO NOTHING
"""
