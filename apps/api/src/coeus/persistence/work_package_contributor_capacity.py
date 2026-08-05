"""Capacity lifecycle owned by package contributor commands."""

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.domain.work_package_contributors import ChangeContributorCommand, ContributorOperation
from coeus.domain.work_packages import ReserveCapacityCommand
from coeus.persistence.capacity_reservations_postgres import reserve_capacity_in_transaction


def reconcile_contributor_capacity(
    connection: Connection,
    command: ChangeContributorCommand,
    package_version: int,
    occurred_at: datetime,
) -> None:
    request = command.request
    if request.operation is ContributorOperation.END:
        connection.execute(
            text(
                "UPDATE capacity_reservations SET state='released',version=version+1,"
                "updated_at=:at WHERE package_id=:package_id AND user_id=:user_id "
                "AND participant_role='contributor' AND state IN ('held','active')"
            ),
            {
                "package_id": request.package_id,
                "user_id": request.contributor_user_id,
                "at": occurred_at,
            },
        )
        return
    plan = request.capacity_plan
    if plan is None:
        return
    package = (
        connection.execute(
            text(
                "SELECT ticket_id,workflow_leg FROM canonical_work_packages "
                "WHERE package_id=:package_id"
            ),
            {"package_id": request.package_id},
        )
        .mappings()
        .one()
    )
    reserve_capacity_in_transaction(
        connection,
        ReserveCapacityCommand(
            plan.reservation_id,
            command.actor_user_id,
            request.contributor_user_id,
            package["ticket_id"],
            WorkflowLeg(package["workflow_leg"]),
            request.package_id,
            plan.starts_at,
            plan.ends_at,
            plan.reserved_minutes,
            plan.idempotency_key,
            package_version,
            "contributor",
        ),
    )
