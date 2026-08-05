"""Immutable, bounded evidence for accountable-owner handover."""

import json
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.work_package_handovers import HandoverWorkPackageCommand


def handover_history_values(
    command: HandoverWorkPackageCommand,
    source_user_id: UUID,
    package_version: int,
    occurred_at: datetime,
) -> dict[str, object]:
    request = command.request
    return {
        "history_id": uuid5(
            NAMESPACE_URL,
            f"coeus:work-package-history:{request.package_id}:{package_version}",
        ),
        "package_id": request.package_id,
        "version": package_version,
        "actor_user_id": command.actor_user_id,
        "evidence": json.dumps(
            {
                "grant_id": str(request.authorising_grant_id),
                "grant_version": request.expected_grant_version,
                "ticket_version": request.expected_ticket_version,
                "ticket_source_hash": request.expected_ticket_source_hash,
                "ownership_version": request.expected_ownership_version,
                "source_user_id": str(source_user_id),
                "target_account_credential_version": (
                    request.expected_target_account_credential_version
                ),
                "target_account_source_hash": request.expected_target_account_source_hash,
                "target_membership_id": str(request.target_membership_id),
                "target_membership_version": request.expected_target_membership_version,
                "target_user_id": str(request.target_user_id),
                "reservation_dispositions": [
                    {
                        "disposition": item.disposition.value,
                        "replacement_reservation_id": (
                            str(item.replacement_reservation_id)
                            if item.replacement_reservation_id is not None
                            else None
                        ),
                        "source_reservation_id": str(item.source_reservation_id),
                    }
                    for item in request.reservations
                ],
            },
            sort_keys=True,
        ),
        "occurred_at": occurred_at,
    }


def append_handover_evidence(
    connection: Connection,
    command: HandoverWorkPackageCommand,
    source_user_id: UUID,
    package_version: int,
    occurred_at: datetime,
) -> None:
    event_id = uuid5(NAMESPACE_URL, f"coeus:work-package-handover:{command.command_id}")
    payload = json.dumps(
        {
            "package_id": str(command.request.package_id),
            "source_user_id": str(source_user_id),
            "target_user_id": str(command.request.target_user_id),
            "version": package_version,
        },
        sort_keys=True,
    )
    values = {
        "event_id": event_id,
        "event_type": "work_package_handed_over",
        "occurred_at": occurred_at,
        "actor_user_id": command.actor_user_id,
        "aggregate_id": command.request.package_id,
        "aggregate_version": package_version,
        "payload": payload,
    }
    connection.execute(
        text(
            "INSERT INTO coeus_audit_events"
            "(event_id,event_type,occurred_at,actor_user_id,metadata) "
            "VALUES (:event_id,:event_type,:occurred_at,:actor_user_id,CAST(:payload AS jsonb))"
        ),
        values,
    )
    connection.execute(
        text(
            "INSERT INTO coeus_outbox"
            "(event_id,aggregate_id,aggregate_version,event_type,payload) "
            "VALUES (:event_id,:aggregate_id,:aggregate_version,:event_type,"
            "CAST(:payload AS jsonb))"
        ),
        values,
    )
