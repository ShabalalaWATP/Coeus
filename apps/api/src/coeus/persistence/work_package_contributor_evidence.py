"""Immutable, privacy-bounded contributor command evidence."""

import json
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.work_package_contributors import ChangeContributorCommand


def append_contributor_evidence(
    connection: Connection,
    command: ChangeContributorCommand,
    package_version: int,
    occurred_at: datetime,
) -> None:
    event_type = f"work_package_contributor_{command.request.operation.value}ed"
    event_id = uuid5(NAMESPACE_URL, f"coeus:{event_type}:{command.command_id}")
    payload = json.dumps(
        {
            "contributor_user_id": str(command.request.contributor_user_id),
            "membership_id": str(command.request.membership_id),
            "package_id": str(command.request.package_id),
            "unit_id": str(command.request.unit_id),
            "version": package_version,
        },
        sort_keys=True,
    )
    values = {
        "event_id": event_id,
        "event_type": event_type,
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


def contributor_history_values(
    command: ChangeContributorCommand,
    package_version: int,
    occurred_at: datetime,
) -> dict[str, object]:
    request = command.request
    return {
        "history_id": _history_id(request.package_id, package_version),
        "package_id": request.package_id,
        "version": package_version,
        "actor_user_id": command.actor_user_id,
        "event_type": f"contributor_{request.operation.value}ed",
        "evidence": json.dumps(
            {
                "account_credential_version": request.expected_account_credential_version,
                "account_source_hash": request.expected_account_source_hash,
                "contributor_user_id": str(request.contributor_user_id),
                "grant_id": str(request.authorising_grant_id),
                "grant_version": request.expected_grant_version,
                "membership_id": str(request.membership_id),
                "membership_version": request.expected_membership_version,
                "ownership_version": request.expected_ownership_version,
            },
            sort_keys=True,
        ),
        "occurred_at": occurred_at,
    }


def _history_id(package_id: UUID, version: int) -> UUID:
    return uuid5(NAMESPACE_URL, f"coeus:work-package-history:{package_id}:{version}")
