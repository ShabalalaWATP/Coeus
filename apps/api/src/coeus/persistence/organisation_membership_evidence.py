"""Authority invalidation and evidence for membership lifecycle commands."""

import json
from datetime import datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.organisation_membership import (
    MembershipMutationCommand,
    MembershipMutationResult,
)


def append_membership_evidence(
    connection: Connection,
    command: MembershipMutationCommand,
    result: MembershipMutationResult,
    occurred_at: datetime,
) -> None:
    request = command.request
    connection.execute(
        text(
            "INSERT INTO effective_authority_epochs"
            "(principal_id,scope_unit_id,epoch,advanced_at) VALUES "
            "(:user_id,:unit_id,1,:occurred_at),(:actor_user_id,:unit_id,1,:occurred_at) "
            "ON CONFLICT (principal_id,scope_unit_id) DO UPDATE SET "
            "epoch=effective_authority_epochs.epoch + 1,advanced_at=EXCLUDED.advanced_at"
        ),
        {**vars(request), "actor_user_id": command.actor_user_id, "occurred_at": occurred_at},
    )
    suffix = {
        "create": "created",
        "update": "updated",
        "end": "ended",
    }[request.operation.value]
    event_type = f"organisation_membership_{suffix}"
    event_id = uuid5(NAMESPACE_URL, f"coeus:{event_type}:{command.command_id}")
    payload = json.dumps(
        {
            "membership_id": str(request.membership_id),
            "user_id": str(request.user_id),
            "unit_id": str(request.unit_id),
            "version": result.version,
            "reason_hash": sha256(request.reason.encode()).hexdigest(),
        },
        sort_keys=True,
    )
    values = {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": occurred_at,
        "actor_user_id": str(command.actor_user_id),
        "unit_id": request.unit_id,
        "membership_id": request.membership_id,
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
VALUES (:event_id,:membership_id,:result_version,:event_type,CAST(:payload AS jsonb))
ON CONFLICT (aggregate_id,aggregate_version,event_type) DO NOTHING
"""
