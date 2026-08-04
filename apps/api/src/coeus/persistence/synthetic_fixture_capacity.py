"""Inspect and write exact synthetic capacity reservation rows."""

from hashlib import sha256

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.synthetic_organisation_fixture import (
    SyntheticFixtureFinding,
    SyntheticFixtureUser,
)
from coeus.persistence.synthetic_fixture_inspection_common import classify, material, row
from coeus.repositories.synthetic_capacity_manifest import (
    SyntheticCapacityReservationSpec,
    synthetic_capacity_reservations,
)
from coeus.repositories.synthetic_organisation_manifest import BASELINE
from coeus.repositories.synthetic_task_manifest import synthetic_task_specs


def inspect_capacity_reservations(
    connection: Connection,
    users: dict[str, SyntheticFixtureUser],
    findings: list[SyntheticFixtureFinding],
    state: list[object],
    creates: dict[str, int],
    unchanged: dict[str, int],
) -> list[SyntheticCapacityReservationSpec]:
    tasks = {item.key: item for item in synthetic_task_specs()}
    missing: list[SyntheticCapacityReservationSpec] = []
    for spec in synthetic_capacity_reservations():
        task = tasks[spec.task_key]
        actor = users[task.manager_username].user_id
        owner = users[task.assignee_username or ""].user_id
        existing = row(connection, "capacity_reservations", "reservation_id", spec.reservation_id)
        expected = {
            "user_id": owner,
            "ticket_id": task.ticket_id,
            "workflow_leg": task.workflow_leg.value,
            "package_id": task.package_id(1),
            "starts_at": spec.starts_at,
            "ends_at": spec.ends_at,
            "reserved_minutes": spec.minutes,
            "state": "active",
            "idempotency_key": f"synthetic-capacity:{spec.key}",
            "actor_user_id": actor,
            "version": 1,
        }
        state.append(("capacity_reservation", spec.key, material(existing)))
        classify(
            existing, expected, spec, "capacity_reservations", findings, missing, creates, unchanged
        )
    return missing


def insert_capacity_reservations(
    connection: Connection,
    specs: tuple[SyntheticCapacityReservationSpec, ...],
    users: dict[str, SyntheticFixtureUser],
) -> None:
    tasks = {item.key: item for item in synthetic_task_specs()}
    for spec in specs:
        task = tasks[spec.task_key]
        key = f"synthetic-capacity:{spec.key}"
        request_hash = sha256(f"{key}:{spec.minutes}".encode()).hexdigest()
        connection.execute(
            text(
                "INSERT INTO capacity_reservations(reservation_id,user_id,ticket_id,workflow_leg,"
                "package_id,starts_at,ends_at,reserved_minutes,state,expires_at,idempotency_key,"
                "request_hash,actor_user_id,version,created_at,updated_at) VALUES "
                "(:id,:user_id,:ticket_id,:leg,:package_id,:starts_at,:ends_at,:minutes,'active',"
                "NULL,:key,:request_hash,:actor_id,1,:created_at,:created_at)"
            ),
            {
                "id": spec.reservation_id,
                "user_id": users[task.assignee_username or ""].user_id,
                "ticket_id": task.ticket_id,
                "leg": task.workflow_leg.value,
                "package_id": task.package_id(1),
                "starts_at": spec.starts_at,
                "ends_at": spec.ends_at,
                "minutes": spec.minutes,
                "key": key,
                "request_hash": request_hash,
                "actor_id": users[task.manager_username].user_id,
                "created_at": BASELINE,
            },
        )
