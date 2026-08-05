"""Atomic audit, outbox and immutable history for workflow-leg transfer."""

# ruff: noqa: E501

import json
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.workflow_leg_transfers import WorkflowLegTransferState


def append_transfer_evidence(
    connection: Connection,
    transfer_id: UUID,
    ticket_id: UUID,
    actor_user_id: UUID,
    state: WorkflowLegTransferState,
    version: int,
    occurred_at: datetime,
) -> None:
    event_type = f"workflow_leg_transfer_{state.value}"
    event_id = uuid5(NAMESPACE_URL, f"coeus:{transfer_id}:{version}:{event_type}")
    payload = json.dumps(
        {"transfer_id": str(transfer_id), "ticket_id": str(ticket_id), "state": state.value},
        sort_keys=True,
    )
    connection.execute(
        text("""INSERT INTO coeus_audit_events
(event_id,event_type,occurred_at,actor_user_id,metadata) VALUES
(:event_id,:event_type,:occurred_at,:actor_user_id,CAST(:payload AS jsonb))"""),
        {
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": occurred_at,
            "actor_user_id": actor_user_id,
            "payload": payload,
        },
    )
    connection.execute(
        text("""INSERT INTO coeus_outbox
(event_id,aggregate_id,aggregate_version,event_type,payload) VALUES
(:event_id,:aggregate_id,:version,:event_type,CAST(:payload AS jsonb))"""),
        {
            "event_id": event_id,
            "aggregate_id": transfer_id,
            "version": version,
            "event_type": event_type,
            "payload": payload,
        },
    )


def append_package_history(
    connection: Connection,
    package_id: UUID,
    package_version: int,
    actor_user_id: UUID,
    transfer_id: UUID,
    source_user_id: UUID | None,
    target_user_id: UUID | None,
    disposition: str,
    occurred_at: datetime,
) -> None:
    evidence = json.dumps(
        {
            "transfer_id": str(transfer_id),
            "disposition": disposition,
            "completed_owner_user_id": str(source_user_id) if source_user_id else None,
            "target_user_id": str(target_user_id) if target_user_id else None,
        },
        sort_keys=True,
    )
    connection.execute(
        text("""INSERT INTO work_package_history
(history_id,package_id,version,actor_user_id,event_type,evidence,occurred_at) VALUES
(:history_id,:package_id,:version,:actor_user_id,'cross_team_transfer',CAST(:evidence AS jsonb),:at)"""),
        {
            "history_id": uuid5(
                NAMESPACE_URL, f"coeus:work-package-history:{package_id}:{package_version}"
            ),
            "package_id": package_id,
            "version": package_version,
            "actor_user_id": actor_user_id,
            "evidence": evidence,
            "at": occurred_at,
        },
    )
