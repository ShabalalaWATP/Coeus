"""Synchronise authoritative ticket package status into the canonical ledger."""

import json
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.tickets import TicketRecord
from coeus.persistence.organisation_authority_validation import transaction_time


def sync_work_package_statuses(
    connection: Connection,
    ticket: TicketRecord,
    actor_user_id: UUID,
) -> tuple[UUID, ...]:
    """Update only changed packages and release reservations on terminal states."""
    if not ticket.work_packages:
        return ()
    now = transaction_time(connection)
    changed: list[UUID] = []
    for package in ticket.work_packages:
        target_state = "complete" if package.status.value == "complete" else "pending"
        current = (
            connection.execute(
                text(_LOCK_PACKAGE),
                {"package_id": package.package_id, "ticket_id": ticket.ticket_id},
            )
            .mappings()
            .first()
        )
        unchanged = current is not None and (
            current["state"] == target_state and current["title"] == package.title
        )
        if current is None or unchanged:
            continue
        blocked_by_dependency = target_state == "complete" and _has_incomplete_predecessor(
            connection, package.package_id
        )
        if blocked_by_dependency:
            raise ValueError("a work package cannot complete before its dependencies")
        version = int(current["version"]) + 1
        connection.execute(
            text(_UPDATE_PACKAGE),
            {
                "package_id": package.package_id,
                "title": package.title,
                "state": target_state,
                "version": version,
                "now": now,
            },
        )
        if target_state == "complete":
            connection.execute(
                text(_RELEASE_RESERVATIONS),
                {"package_id": package.package_id, "now": now},
            )
        _append_history(connection, package.package_id, actor_user_id, version, target_state, now)
        changed.append(package.package_id)
    return tuple(changed)


def _has_incomplete_predecessor(connection: Connection, package_id: UUID) -> bool:
    return (
        connection.execute(
            text(_INCOMPLETE_PREDECESSOR), {"package_id": package_id}
        ).scalar_one_or_none()
        is not None
    )


def _append_history(
    connection: Connection,
    package_id: UUID,
    actor_user_id: UUID,
    version: int,
    state: str,
    now: datetime,
) -> None:
    history_id = uuid5(NAMESPACE_URL, f"coeus:work-package:{package_id}:{version}")
    connection.execute(
        text(_INSERT_HISTORY),
        {
            "history_id": history_id,
            "package_id": package_id,
            "version": version,
            "actor_id": actor_user_id,
            "evidence": json.dumps({"state": state, "source": "ticket-package-status-v1"}),
            "now": now,
        },
    )


_LOCK_PACKAGE = """
SELECT state,title,version
FROM canonical_work_packages
WHERE package_id=:package_id AND ticket_id=:ticket_id
FOR UPDATE
"""

_INCOMPLETE_PREDECESSOR = """
SELECT 1
FROM work_package_dependencies dependency
JOIN canonical_work_packages predecessor
  ON predecessor.package_id=dependency.predecessor_package_id
WHERE dependency.package_id=:package_id AND predecessor.state<>'complete'
LIMIT 1
"""

_UPDATE_PACKAGE = """
UPDATE canonical_work_packages
SET title=:title,state=:state,
    remaining_minutes=CASE
      WHEN :state='complete' THEN 0
      WHEN estimated_minutes IS NOT NULL THEN estimated_minutes
      ELSE NULL
    END,
    version=:version,updated_at=:now
WHERE package_id=:package_id
"""

_RELEASE_RESERVATIONS = """
UPDATE capacity_reservations
SET state='released',version=version+1,updated_at=:now
WHERE package_id=:package_id AND state IN ('held','active')
"""

_INSERT_HISTORY = """
INSERT INTO work_package_history(
 history_id,package_id,version,actor_user_id,event_type,evidence,occurred_at)
VALUES (
 :history_id,:package_id,:version,:actor_id,'status_changed',CAST(:evidence AS jsonb),:now)
"""
