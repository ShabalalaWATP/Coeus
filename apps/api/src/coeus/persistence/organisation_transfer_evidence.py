"""Audit, outbox and epoch evidence for personnel transfers."""

import json
from datetime import datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.organisation_transfer import PersonnelTransferCommand, PersonnelTransferResult


def append_transfer_evidence(
    connection: Connection,
    command: PersonnelTransferCommand,
    result: PersonnelTransferResult,
    occurred_at: datetime,
) -> None:
    request = command.request
    if result.status.value == "applied":
        connection.execute(
            text(
                "INSERT INTO effective_authority_epochs"
                "(principal_id,scope_unit_id,epoch,advanced_at) VALUES "
                "(:user_id,:source_unit_id,1,:occurred_at),"
                "(:user_id,:target_unit_id,1,:occurred_at) "
                "ON CONFLICT (principal_id,scope_unit_id) DO UPDATE SET "
                "epoch=effective_authority_epochs.epoch + 1,advanced_at=EXCLUDED.advanced_at"
            ),
            {**vars(request), "occurred_at": occurred_at},
        )
    event_type = f"organisation_personnel_transfer_{result.status.value}"
    version = 1 if result.status.value == "pending" else 2
    event_id = uuid5(NAMESPACE_URL, f"coeus:{event_type}:{command.command_id}")
    payload = json.dumps(
        {
            "command_id": str(command.command_id),
            "user_id": str(request.user_id),
            "source_unit_id": str(request.source_unit_id),
            "target_unit_id": str(request.target_unit_id),
            "effective_at": request.effective_at.isoformat(),
            "status": result.status.value,
            "failure_code": result.failure_code,
            "reason_hash": sha256(request.reason.encode()).hexdigest(),
        },
        sort_keys=True,
    )
    values = {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": occurred_at,
        "actor_user_id": str(command.actor_user_id),
        "command_id": command.command_id,
        "version": version,
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
VALUES (:event_id,:command_id,:version,:event_type,CAST(:payload AS jsonb))
ON CONFLICT (aggregate_id,aggregate_version,event_type) DO NOTHING
"""
