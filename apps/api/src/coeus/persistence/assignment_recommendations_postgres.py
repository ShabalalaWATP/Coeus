"""Serializable preparation of deterministic assignment recommendations."""

import json
from datetime import datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from coeus.application.ports.assignment_recommendations import AssignmentRecommendationStore
from coeus.domain.assignment_recommendations import (
    AcceptRecommendationRequest,
    AssignmentRecommendationAcceptance,
    AssignmentRecommendationConflict,
    AssignmentRecommendationDenied,
    AssignmentRecommendationPreview,
    ExclusionCode,
    PrepareRecommendationRequest,
    RankedAssignmentCandidate,
    demand_hash,
)
from coeus.persistence.assignment_recommendation_queries import authorised_units
from coeus.persistence.assignment_recommendation_ranking import rank_candidates
from coeus.persistence.organisation_authority_validation import transaction_time
from coeus.persistence.serializable_retry import retry_serializable_once


class PostgresAssignmentRecommendationStore(AssignmentRecommendationStore):
    def __init__(self, engine: Engine, *, hold_minutes: int = 15) -> None:
        if not 5 <= hold_minutes <= 30:
            raise ValueError("assignment hold lifetime must be between 5 and 30 minutes")
        self._engine = engine
        self._hold_minutes = hold_minutes

    def prepare(
        self, actor_user_id: UUID, request: PrepareRecommendationRequest
    ) -> AssignmentRecommendationPreview:
        return retry_serializable_once(lambda: self._prepare_once(actor_user_id, request))

    def _prepare_once(
        self, actor_user_id: UUID, request: PrepareRecommendationRequest
    ) -> AssignmentRecommendationPreview:
        connection = self._engine.connect().execution_options(isolation_level="SERIALIZABLE")
        try:
            with connection.begin():
                now = transaction_time(connection)
                connection.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                    {
                        "key": (
                            f"assignment-demand:{request.demand.ticket_id}:"
                            f"{request.demand.workflow_leg}"
                        )
                    },
                )
                _expire_holds(connection, now)
                ticket_version = _ticket_version(connection, request.demand.ticket_id)
                units = authorised_units(
                    connection,
                    actor_user_id,
                    request.demand.workflow_leg,
                    now,
                    request.unit_id,
                )
                if not units:
                    raise AssignmentRecommendationDenied("no current assignment authority")
                candidates, exclusions, evidence = rank_candidates(
                    connection, units, request.demand, now
                )
                if not candidates:
                    raise AssignmentRecommendationDenied("no eligible assignment candidate")
                return _persist(
                    connection,
                    actor_user_id,
                    request,
                    ticket_version,
                    candidates,
                    exclusions,
                    evidence,
                    now,
                    self._hold_minutes,
                )
        finally:
            connection.close()

    def acceptance(
        self, actor_user_id: UUID, request: AcceptRecommendationRequest
    ) -> AssignmentRecommendationAcceptance:
        with self._engine.connect() as connection, connection.begin():
            now = transaction_time(connection)
            row = (
                connection.execute(
                    text(_ACCEPTANCE),
                    {
                        "recommendation_id": request.recommendation_id,
                        "actor_id": actor_user_id,
                        "user_id": request.selected_analyst_user_id,
                        "unit_id": request.selected_unit_id,
                    },
                )
                .mappings()
                .first()
            )
            if (
                row is None
                or row["state"] != "prepared"
                or row["expires_at"] <= now
                or row["preview_hash"] != request.preview_hash
            ):
                raise AssignmentRecommendationConflict("assignment recommendation is not current")
            overridden = int(row["rank"]) != 1
            reason = request.override_reason.strip()
            if overridden and not reason:
                raise AssignmentRecommendationDenied("a soft override requires a reason")
            if not overridden and reason:
                raise AssignmentRecommendationDenied(
                    "an override reason requires another candidate"
                )
            return AssignmentRecommendationAcceptance(
                request.recommendation_id,
                request.preview_hash,
                actor_user_id,
                request.selected_unit_id,
                request.selected_analyst_user_id,
                reason,
            )


def _ticket_version(connection: Connection, ticket_id: UUID) -> int:
    value = connection.execute(
        text("SELECT version FROM coeus_ticket_aggregates WHERE ticket_id=:ticket_id"),
        {"ticket_id": ticket_id},
    ).scalar_one_or_none()
    if value is None:
        raise AssignmentRecommendationDenied("ticket is unavailable")
    return int(value)


def _persist(
    connection: Connection,
    actor_id: UUID,
    request: PrepareRecommendationRequest,
    ticket_version: int,
    candidates: tuple[RankedAssignmentCandidate, ...],
    exclusions: tuple[tuple[ExclusionCode, int], ...],
    evidence: dict[UUID, str],
    now: datetime,
    hold_minutes: int,
) -> AssignmentRecommendationPreview:
    demand = request.demand
    estimate_id, recommendation_id, hold_id = uuid4(), uuid4(), uuid4()
    source_hash = demand_hash(actor_id, request)
    version = int(
        connection.execute(
            text(
                "SELECT coalesce(max(version),0)+1 FROM assignment_demand_estimates "
                "WHERE ticket_id=:ticket_id AND workflow_leg=:workflow_leg"
            ),
            {"ticket_id": demand.ticket_id, "workflow_leg": demand.workflow_leg.value},
        ).scalar_one()
    )
    preview_hash = _preview_hash(source_hash, ticket_version, candidates, exclusions, evidence)
    expires_at = now + timedelta(minutes=hold_minutes)
    connection.execute(
        text(_INSERT_ESTIMATE),
        {
            "estimate_id": estimate_id,
            "ticket_id": demand.ticket_id,
            "workflow_leg": demand.workflow_leg.value,
            "version": version,
            "effort_min": demand.effort_min_minutes,
            "effort_max": demand.effort_max_minutes,
            "start": demand.window_start,
            "deadline": demand.deadline,
            "capabilities": list(demand.capability_ids),
            "actor_id": actor_id,
            "source_hash": source_hash,
            "now": now,
        },
    )
    connection.execute(
        text(_INSERT_RECOMMENDATION),
        {
            "recommendation_id": recommendation_id,
            "estimate_id": estimate_id,
            "actor_id": actor_id,
            "ticket_version": ticket_version,
            "preview_hash": preview_hash,
            "expires_at": expires_at,
            "now": now,
            "exclusion_counts": json.dumps({code.value: count for code, count in exclusions}),
        },
    )
    for candidate in candidates:
        connection.execute(
            text(_INSERT_CANDIDATE),
            {
                "recommendation_id": recommendation_id,
                "unit_id": candidate.unit_id,
                "user_id": candidate.analyst_user_id,
                "rank": candidate.rank,
                "minutes": candidate.assignable_minutes,
                "wip": candidate.active_wip,
                "evidence_hash": evidence[candidate.analyst_user_id],
                "explanation_codes": [code.value for code in candidate.explanation_codes],
            },
        )
    recommended = candidates[0]
    connection.execute(
        text(_INSERT_HOLD),
        {
            "hold_id": hold_id,
            "recommendation_id": recommendation_id,
            "ticket_id": demand.ticket_id,
            "unit_id": recommended.unit_id,
            "user_id": recommended.analyst_user_id,
            "minutes": demand.effort_max_minutes,
            "start": demand.window_start,
            "deadline": demand.deadline,
            "expires_at": expires_at,
            "now": now,
        },
    )
    return AssignmentRecommendationPreview(
        recommendation_id,
        estimate_id,
        version,
        hold_id,
        preview_hash,
        expires_at,
        candidates,
        exclusions,
    )


def _preview_hash(
    source: str,
    ticket_version: int,
    candidates: tuple[RankedAssignmentCandidate, ...],
    exclusions: tuple[tuple[ExclusionCode, int], ...],
    evidence: dict[UUID, str],
) -> str:
    value = {
        "candidates": [
            [
                str(item.unit_id),
                str(item.analyst_user_id),
                item.rank,
                item.assignable_minutes,
                item.active_wip,
                evidence[item.analyst_user_id],
            ]
            for item in candidates
        ],
        "exclusions": [[code.value, count] for code, count in exclusions],
        "source": source,
        "ticket_version": ticket_version,
    }
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _expire_holds(connection: Connection, now: datetime) -> None:
    connection.execute(
        text(
            "UPDATE assignment_demand_holds SET state='expired',updated_at=:now "
            "WHERE state='active' AND expires_at<=:now"
        ),
        {"now": now},
    )
    connection.execute(
        text(
            "UPDATE assignment_recommendations SET state='expired',updated_at=:now "
            "WHERE state='prepared' AND expires_at<=:now"
        ),
        {"now": now},
    )


_INSERT_ESTIMATE = """INSERT INTO assignment_demand_estimates(
 estimate_id,ticket_id,workflow_leg,version,effort_min_minutes,effort_max_minutes,
 window_start,deadline,capability_ids,created_by_user_id,source_hash,created_at)
VALUES (:estimate_id,:ticket_id,:workflow_leg,:version,:effort_min,:effort_max,
 :start,:deadline,:capabilities,:actor_id,:source_hash,:now)"""
_INSERT_RECOMMENDATION = """INSERT INTO assignment_recommendations(
 recommendation_id,estimate_id,actor_user_id,ticket_version,preview_hash,state,
 exclusion_counts,expires_at,created_at,updated_at) VALUES (
 :recommendation_id,:estimate_id,:actor_id,:ticket_version,:preview_hash,'prepared',
 CAST(:exclusion_counts AS jsonb),
 :expires_at,:now,:now)"""
_INSERT_CANDIDATE = """INSERT INTO assignment_recommendation_candidates(
 recommendation_id,unit_id,analyst_user_id,rank,assignable_minutes,active_wip,
 explanation_codes,evidence_hash)
VALUES (:recommendation_id,:unit_id,:user_id,:rank,:minutes,:wip,
 :explanation_codes,:evidence_hash)"""
_INSERT_HOLD = """INSERT INTO assignment_demand_holds(
 hold_id,recommendation_id,ticket_id,unit_id,held_minutes,starts_at,ends_at,
 state,expires_at,created_at,updated_at) VALUES (
 :hold_id,:recommendation_id,:ticket_id,:unit_id,:minutes,:start,:deadline,
 'active',:expires_at,:now,:now)"""
_ACCEPTANCE = """SELECT recommendation.state,recommendation.expires_at,
 recommendation.preview_hash,candidate.rank
FROM assignment_recommendations recommendation
JOIN assignment_recommendation_candidates candidate
  ON candidate.recommendation_id=recommendation.recommendation_id
WHERE recommendation.recommendation_id=:recommendation_id
  AND recommendation.actor_user_id=:actor_id
  AND candidate.analyst_user_id=:user_id AND candidate.unit_id=:unit_id"""
