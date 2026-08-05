"""Atomic recommendation validation, demand planning and capacity reservation."""

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.assignment_recommendations import (
    AssignmentDemand,
    AssignmentRecommendationAcceptance,
    AssignmentRecommendationConflict,
    AssignmentRecommendationDenied,
)
from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.domain.work_packages import CapacityReservation, ReserveCapacityCommand
from coeus.persistence.assignment_recommendation_queries import authorised_units
from coeus.persistence.assignment_recommendation_ranking import rank_candidates
from coeus.persistence.capacity_reservations_postgres import reserve_capacity_in_transaction
from coeus.persistence.organisation_authority_validation import transaction_time


@dataclass(frozen=True)
class AcceptedRecommendation:
    reservation: CapacityReservation
    decision_type: str


def accept_recommendation_in_transaction(
    connection: Connection,
    acceptance: AssignmentRecommendationAcceptance,
    ticket_id: UUID,
    workflow_leg: WorkflowLeg,
    package_ids: tuple[UUID, ...],
    expected_ticket_version: int,
) -> AcceptedRecommendation:
    now = transaction_time(connection)
    row = _lock_evidence(
        connection, acceptance.recommendation_id, acceptance.selected_analyst_user_id
    )
    demand = _validate_bound_evidence(
        row, acceptance, ticket_id, workflow_leg, expected_ticket_version, package_ids, now
    )
    units = authorised_units(
        connection,
        acceptance.actor_user_id,
        workflow_leg,
        now,
        acceptance.selected_unit_id,
    )
    if units != (acceptance.selected_unit_id,):
        raise AssignmentRecommendationDenied("current assignment authority is unavailable")
    candidates, _, _ = rank_candidates(
        connection,
        units,
        demand,
        now,
        exclude_recommendation_id=acceptance.recommendation_id,
    )
    selected = next(
        (
            item
            for item in candidates
            if item.analyst_user_id == acceptance.selected_analyst_user_id
        ),
        None,
    )
    if selected is None:
        raise AssignmentRecommendationDenied("selected analyst is no longer eligible")
    recommended_id = UUID(str(row["recommended_analyst_user_id"]))
    overridden = acceptance.selected_analyst_user_id != recommended_id
    reason = acceptance.override_reason.strip()
    if overridden and not reason:
        raise AssignmentRecommendationDenied("a soft override requires a reason")
    if not overridden and reason:
        raise AssignmentRecommendationDenied("an override reason requires another candidate")
    package_id, package_version = _plan_package(
        connection, package_ids[0], demand, acceptance.selected_analyst_user_id, now
    )
    reservation = reserve_capacity_in_transaction(
        connection,
        ReserveCapacityCommand(
            reservation_id=uuid5(
                NAMESPACE_URL, f"coeus:assignment-recommendation:{acceptance.recommendation_id}"
            ),
            actor_user_id=acceptance.actor_user_id,
            user_id=acceptance.selected_analyst_user_id,
            ticket_id=ticket_id,
            workflow_leg=workflow_leg,
            package_id=package_id,
            starts_at=demand.window_start,
            ends_at=demand.deadline,
            reserved_minutes=demand.effort_max_minutes,
            idempotency_key=f"assignment-recommendation:{acceptance.recommendation_id}",
            expected_package_version=package_version,
        ),
    )
    decision_type = "soft_override" if overridden else "accepted"
    _record_decision(connection, acceptance, recommended_id, decision_type, reason, now)
    return AcceptedRecommendation(reservation, decision_type)


def _lock_evidence(
    connection: Connection, recommendation_id: UUID, selected_user_id: UUID
) -> RowMapping:
    row = (
        connection.execute(
            text(_EVIDENCE),
            {"recommendation_id": recommendation_id, "selected_user_id": selected_user_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise AssignmentRecommendationConflict("assignment recommendation is unavailable")
    return row


def _validate_bound_evidence(
    row: RowMapping,
    acceptance: AssignmentRecommendationAcceptance,
    ticket_id: UUID,
    workflow_leg: WorkflowLeg,
    ticket_version: int,
    package_ids: tuple[UUID, ...],
    now: datetime,
) -> AssignmentDemand:
    if (
        row["state"] != "prepared"
        or row["hold_state"] != "active"
        or row["expires_at"] <= now
        or row["hold_expires_at"] <= now
        or row["actor_user_id"] != acceptance.actor_user_id
        or row["preview_hash"] != acceptance.preview_hash
        or row["ticket_id"] != ticket_id
        or row["workflow_leg"] != workflow_leg.value
        or int(row["ticket_version"]) != ticket_version
        or not package_ids
    ):
        raise AssignmentRecommendationConflict("assignment recommendation is no longer current")
    if row["selected_rank"] is None or row["selected_unit_id"] != acceptance.selected_unit_id:
        raise AssignmentRecommendationDenied(
            "selected candidate was not in the reviewed recommendation"
        )
    return AssignmentDemand(
        ticket_id=ticket_id,
        workflow_leg=workflow_leg,
        effort_min_minutes=int(row["effort_min_minutes"]),
        effort_max_minutes=int(row["effort_max_minutes"]),
        window_start=row["window_start"],
        deadline=row["deadline"],
        capability_ids=tuple(row["capability_ids"]),
    )


def _plan_package(
    connection: Connection,
    package_id: UUID,
    demand: AssignmentDemand,
    analyst_user_id: UUID,
    now: datetime,
) -> tuple[UUID, int]:
    row = (
        connection.execute(
            text(_PLAN_PACKAGE),
            {
                "package_id": package_id,
                "user_id": analyst_user_id,
                "minutes": demand.effort_max_minutes,
                "deadline": demand.deadline,
                "now": now,
            },
        )
        .mappings()
        .first()
    )
    if row is None:
        raise AssignmentRecommendationConflict("assignment work package cannot be reserved")
    return UUID(str(row["package_id"])), int(row["version"])


def _record_decision(
    connection: Connection,
    acceptance: AssignmentRecommendationAcceptance,
    recommended_id: UUID,
    decision_type: str,
    reason: str,
    now: datetime,
) -> None:
    reason_hash = sha256(reason.encode()).hexdigest()
    connection.execute(
        text(_INSERT_DECISION),
        {
            "decision_id": uuid5(
                NAMESPACE_URL, f"coeus:assignment-decision:{acceptance.recommendation_id}"
            ),
            "recommendation_id": acceptance.recommendation_id,
            "actor_id": acceptance.actor_user_id,
            "unit_id": acceptance.selected_unit_id,
            "user_id": acceptance.selected_analyst_user_id,
            "recommended_id": recommended_id,
            "decision_type": decision_type,
            "reason": reason,
            "reason_hash": reason_hash,
            "now": now,
        },
    )
    connection.execute(
        text(
            "UPDATE assignment_recommendations SET state='accepted',updated_at=:now "
            "WHERE recommendation_id=:recommendation_id AND state='prepared'"
        ),
        {"recommendation_id": acceptance.recommendation_id, "now": now},
    )
    connection.execute(
        text(
            "UPDATE assignment_demand_holds SET state='consumed',updated_at=:now "
            "WHERE recommendation_id=:recommendation_id AND state='active'"
        ),
        {"recommendation_id": acceptance.recommendation_id, "now": now},
    )


_EVIDENCE = """
SELECT recommendation.*,estimate.ticket_id,estimate.workflow_leg,estimate.effort_min_minutes,
       estimate.effort_max_minutes,estimate.window_start,estimate.deadline,estimate.capability_ids,
       hold.state AS hold_state,hold.expires_at AS hold_expires_at,
       selected.rank AS selected_rank,selected.unit_id AS selected_unit_id,
       (SELECT analyst_user_id FROM assignment_recommendation_candidates
        WHERE recommendation_id=recommendation.recommendation_id AND rank=1
       ) AS recommended_analyst_user_id
FROM assignment_recommendations recommendation
JOIN assignment_demand_estimates estimate ON estimate.estimate_id=recommendation.estimate_id
JOIN assignment_demand_holds hold ON hold.recommendation_id=recommendation.recommendation_id
LEFT JOIN assignment_recommendation_candidates selected
  ON selected.recommendation_id=recommendation.recommendation_id
 AND selected.analyst_user_id=:selected_user_id
WHERE recommendation.recommendation_id=:recommendation_id
FOR UPDATE OF recommendation,hold
"""

_PLAN_PACKAGE = """
UPDATE canonical_work_packages SET state='ready',accountable_user_id=:user_id,
 estimated_minutes=:minutes,remaining_minutes=:minutes,due_at=:deadline,
 version=version+1,updated_at=:now
WHERE package_id=:package_id AND state='pending' AND accountable_user_id=:user_id
RETURNING package_id,version
"""

_INSERT_DECISION = """
INSERT INTO assignment_recommendation_decisions(
 decision_id,recommendation_id,actor_user_id,selected_unit_id,selected_analyst_user_id,
 recommended_analyst_user_id,decision_type,reason,reason_hash,occurred_at)
VALUES (:decision_id,:recommendation_id,:actor_id,:unit_id,:user_id,:recommended_id,
 :decision_type,:reason,:reason_hash,:now)
"""
