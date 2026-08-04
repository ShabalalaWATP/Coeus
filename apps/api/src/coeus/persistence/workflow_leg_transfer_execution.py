"""Acceptance mutation helpers for cross-team workflow-leg transfer."""

# ruff: noqa: E501

from dataclasses import replace
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.team_task_ownership import WorkflowLeg, delivery_route_for_leg
from coeus.domain.tickets import AnalystAssignment, RoutingRoute, TicketRecord
from coeus.domain.work_packages import ReserveCapacityCommand
from coeus.domain.workflow_leg_transfers import PackageTransferDisposition
from coeus.persistence.capacity_reservations_postgres import reserve_capacity_in_transaction
from coeus.persistence.codec import encode_value
from coeus.persistence.state_store import _shadow_ticket_payload
from coeus.persistence.workflow_leg_transfer_evidence import append_package_history


def update_ticket_assignment(
    connection: Connection,
    ticket: TicketRecord,
    transfer: RowMapping,
    actor_user_id: UUID,
    occurred_at: datetime,
) -> int:
    leg = WorkflowLeg(transfer["workflow_leg"])
    if leg is WorkflowLeg.QC:
        updated = replace(
            ticket,
            qc_reviewer_user_id=transfer["target_user_id"],
            qc_claimed_at=occurred_at,
        )
        _shadow_ticket_payload(connection, {"tickets": [encode_value(updated)]}, reconcile=False)
        return int(
            connection.execute(
                text("SELECT version FROM coeus_ticket_aggregates WHERE ticket_id=:id"),
                {"id": ticket.ticket_id},
            ).scalar_one()
        )
    route = RoutingRoute(delivery_route_for_leg(leg))
    other_source_leg = connection.execute(
        text("""SELECT 1 FROM team_task_ownership
WHERE ticket_id=:ticket_id AND owning_unit_id=:source_unit_id AND workflow_leg<>:workflow_leg
AND state='active' AND workflow_leg IN (:route_leg_a,:route_leg_b) LIMIT 1"""),
        {
            "ticket_id": transfer["ticket_id"],
            "source_unit_id": transfer["source_unit_id"],
            "workflow_leg": leg.value,
            "route_leg_a": "rfa" if route is RoutingRoute.RFA else "cm_collection",
            "route_leg_b": "rfa" if route is RoutingRoute.RFA else "cm_analysis",
        },
    ).scalar_one_or_none()
    assignments = tuple(
        replace(item, active=False)
        if other_source_leg is None
        and item.active
        and item.route is route
        and item.team_id == transfer["source_unit_id"]
        else item
        for item in ticket.analyst_assignments
    )
    team_name = connection.execute(
        text("SELECT name FROM organisation_units WHERE unit_id=:id"),
        {"id": transfer["target_unit_id"]},
    ).scalar_one()
    target = AnalystAssignment(
        uuid5(NAMESPACE_URL, f"coeus:workflow-leg-transfer-assignment:{transfer['transfer_id']}"),
        ticket.ticket_id,
        transfer["target_user_id"],
        actor_user_id,
        route,
        occurred_at,
        transfer["target_unit_id"],
        team_name,
        True,
    )
    updated = replace(ticket, analyst_assignments=(*assignments, target))
    _shadow_ticket_payload(connection, {"tickets": [encode_value(updated)]}, reconcile=False)
    return int(
        connection.execute(
            text("SELECT version FROM coeus_ticket_aggregates WHERE ticket_id=:id"),
            {"id": ticket.ticket_id},
        ).scalar_one()
    )


def apply_package_dispositions(
    connection: Connection,
    transfer: RowMapping,
    packages: tuple[RowMapping, ...],
    actor_user_id: UUID,
    occurred_at: datetime,
    policy_buffer_minutes: int,
) -> None:
    plans = {
        row["package_id"]: row
        for row in connection.execute(
            text(
                "SELECT * FROM workflow_leg_transfer_packages WHERE transfer_id=:id ORDER BY package_id FOR UPDATE"
            ),
            {"id": transfer["transfer_id"]},
        ).mappings()
    }
    for package in packages:
        plan = plans[package["package_id"]]
        disposition = PackageTransferDisposition(plan["disposition"])
        if disposition is PackageTransferDisposition.RETAIN:
            continue
        _release_reservations(connection, package["package_id"], occurred_at)
        if disposition is PackageTransferDisposition.TRANSFER:
            _transfer_package(
                connection,
                transfer,
                package,
                plan,
                actor_user_id,
                occurred_at,
                policy_buffer_minutes,
            )
        else:
            state = (
                "complete" if disposition is PackageTransferDisposition.COMPLETE else "cancelled"
            )
            version = int(
                connection.execute(
                    text("""UPDATE canonical_work_packages SET state=:state,
remaining_minutes=CASE WHEN :state='complete' THEN 0 ELSE remaining_minutes END,
blocked_code=NULL,blocked_note='',review_at=NULL,
version=version+1,updated_at=:at WHERE package_id=:id AND version=:version RETURNING version"""),
                    {
                        "state": state,
                        "at": occurred_at,
                        "id": package["package_id"],
                        "version": package["version"],
                    },
                ).scalar_one()
            )
            _end_participants(connection, package["package_id"], occurred_at)
            append_package_history(
                connection,
                package["package_id"],
                version,
                actor_user_id,
                transfer["transfer_id"],
                package["accountable_user_id"],
                None,
                disposition.value,
                occurred_at,
            )


def _transfer_package(
    connection: Connection,
    transfer: RowMapping,
    package: RowMapping,
    plan: RowMapping,
    actor: UUID,
    at: datetime,
    buffer: int,
) -> None:
    version = int(
        connection.execute(
            text("""UPDATE canonical_work_packages SET
owning_unit_id=:unit_id,accountable_user_id=:user_id,version=version+1,updated_at=:at
WHERE package_id=:id AND version=:version RETURNING version"""),
            {
                "unit_id": transfer["target_unit_id"],
                "user_id": transfer["target_user_id"],
                "at": at,
                "id": package["package_id"],
                "version": package["version"],
            },
        ).scalar_one()
    )
    _end_participants(connection, package["package_id"], at)
    connection.execute(
        text("""INSERT INTO work_package_participants
(package_id,user_id,role,active,created_at) VALUES(:id,:user_id,'accountable',true,:at)
ON CONFLICT(package_id,user_id,role) DO UPDATE SET active=true,created_at=:at,ended_at=NULL"""),
        {"id": package["package_id"], "user_id": transfer["target_user_id"], "at": at},
    )
    reserve_capacity_in_transaction(
        connection,
        ReserveCapacityCommand(
            plan["reservation_id"],
            actor,
            transfer["target_user_id"],
            transfer["ticket_id"],
            WorkflowLeg(transfer["workflow_leg"]),
            package["package_id"],
            plan["starts_at"],
            plan["ends_at"],
            int(plan["reserved_minutes"]),
            plan["reservation_idempotency_key"],
            version,
        ),
        policy_buffer_minutes=buffer,
    )
    connection.execute(
        text("""INSERT INTO workflow_leg_transfer_team_holds
(hold_id,transfer_id,package_id,target_unit_id,starts_at,ends_at,reserved_minutes,state,created_at)
VALUES(:hold_id,:transfer_id,:package_id,:unit_id,:starts_at,:ends_at,:minutes,'active',:at)"""),
        {
            "hold_id": uuid5(
                NAMESPACE_URL,
                f"coeus:workflow-leg-transfer-hold:{transfer['transfer_id']}:{package['package_id']}",
            ),
            "transfer_id": transfer["transfer_id"],
            "package_id": package["package_id"],
            "unit_id": transfer["target_unit_id"],
            "starts_at": plan["starts_at"],
            "ends_at": plan["ends_at"],
            "minutes": plan["reserved_minutes"],
            "at": at,
        },
    )
    append_package_history(
        connection,
        package["package_id"],
        version,
        actor,
        transfer["transfer_id"],
        package["accountable_user_id"],
        transfer["target_user_id"],
        "transfer",
        at,
    )


def _release_reservations(connection: Connection, package_id: UUID, at: datetime) -> None:
    connection.execute(
        text("""UPDATE capacity_reservations SET state='released',version=version+1,
updated_at=:at WHERE package_id=:id AND state IN ('held','active')"""),
        {"id": package_id, "at": at},
    )


def _end_participants(connection: Connection, package_id: UUID, at: datetime) -> None:
    connection.execute(
        text("""UPDATE work_package_participants SET active=false,ended_at=:at
WHERE package_id=:id AND active"""),
        {"id": package_id, "at": at},
    )
