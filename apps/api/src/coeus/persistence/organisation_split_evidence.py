"""Audit, outbox and authority evidence for organisation splits."""

import json
from datetime import datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.organisation_split import (
    OrganisationSplitCommand,
    OrganisationSplitImpact,
    OrganisationSplitResult,
)
from coeus.persistence import organisation_split_sql as sql


def append_split_evidence(
    connection: Connection,
    command: OrganisationSplitCommand,
    result: OrganisationSplitResult,
    impact: OrganisationSplitImpact,
    occurred_at: datetime,
) -> None:
    request = command.plan.request
    successor_ids = [str(item.unit_id) for item in request.successors]
    connection.execute(
        text(sql.ADVANCE_EPOCHS),
        {
            "source_id": request.source.unit_id,
            "parent_id": request.parent.unit_id,
            "successor_ids": successor_ids,
            "occurred_at": occurred_at,
        },
    )
    event_id = uuid5(NAMESPACE_URL, f"coeus:organisation:split:{command.command_id}")
    payload = json.dumps(
        {
            "source_unit_id": str(request.source.unit_id),
            "parent_unit_id": str(request.parent.unit_id),
            "successor_unit_ids": successor_ids,
            "disposition_count": len(command.plan.dispositions),
            "state_digest": impact.state_digest,
            "reason_hash": sha256(request.reason.encode()).hexdigest(),
        },
        sort_keys=True,
    )
    values = {
        "event_id": event_id,
        "event_type": "organisation_unit_split",
        "occurred_at": occurred_at,
        "actor_user_id": str(command.actor_user_id),
        "aggregate_id": request.parent.unit_id,
        "aggregate_version": result.parent.expected_version,
        "payload": payload,
    }
    connection.execute(text(sql.INSERT_AUDIT), values)
    connection.execute(text(sql.INSERT_OUTBOX), values)
