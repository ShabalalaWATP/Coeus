"""Deterministic, fail-closed ranking over relational assignment evidence."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.assignment_recommendations import (
    AssignmentDemand,
    ExclusionCode,
    RankedAssignmentCandidate,
    RecommendationCode,
)
from coeus.domain.capacity_forecast import CapacityForecast
from coeus.persistence.assignment_capacity_batch import batch_person_forecasts
from coeus.persistence.assignment_recommendation_queries import (
    active_team_hold_minutes,
    capability_counts,
    evidence_hash,
    exclusion_pairs,
    roster_rows,
)
from coeus.persistence.identity_account_projection import active_analyst_role

MAX_EVALUATED_CANDIDATES = 500
MAX_RETURNED_CANDIDATES = 10


def rank_candidates(
    connection: Connection,
    unit_ids: tuple[UUID, ...],
    demand: AssignmentDemand,
    at: datetime,
    exclude_recommendation_id: UUID | None = None,
) -> tuple[
    tuple[RankedAssignmentCandidate, ...],
    tuple[tuple[ExclusionCode, int], ...],
    dict[UUID, str],
]:
    roster = roster_rows(connection, unit_ids, demand.window_start, demand.deadline)
    if len(roster) > MAX_EVALUATED_CANDIDATES:
        raise RuntimeError("assignment recommendation cohort is too large")
    user_ids = tuple(UUID(str(row["user_id"])) for row in roster)
    team_caps, person_caps = capability_counts(
        connection,
        unit_ids,
        user_ids,
        demand.capability_ids,
        demand.window_start,
        demand.deadline,
    )
    required = len(demand.capability_ids)
    forecasts = batch_person_forecasts(connection, user_ids, demand.window_start, demand.deadline)
    exclusions: Counter[ExclusionCode] = Counter()
    eligible: list[tuple[UUID, UUID, int, int, str]] = []
    for row in roster:
        user_id = UUID(str(row["user_id"]))
        result = _candidate(row, demand, team_caps, person_caps, required, forecasts.get(user_id))
        if isinstance(result, _InternalExclusion):
            exclusions[_safe_code(result)] += 1
        else:
            eligible.append(result)
    team_minutes: defaultdict[UUID, int] = defaultdict(int)
    for unit_id, _, minutes, _, _ in eligible:
        team_minutes[unit_id] += minutes
    unavailable_teams = {
        unit_id
        for unit_id, minutes in team_minutes.items()
        if minutes
        - active_team_hold_minutes(
            connection,
            unit_id,
            demand.window_start,
            demand.deadline,
            at,
            exclude_recommendation_id,
        )
        < demand.effort_max_minutes
    }
    if unavailable_teams:
        removed = sum(1 for item in eligible if item[0] in unavailable_teams)
        exclusions[ExclusionCode.CAPACITY_UNAVAILABLE] += removed
        eligible = [item for item in eligible if item[0] not in unavailable_teams]
    eligible.sort(key=lambda item: (item[3], -item[2], str(item[0]), str(item[1])))
    candidates = tuple(
        RankedAssignmentCandidate(
            unit_id=unit_id,
            analyst_user_id=user_id,
            rank=index,
            assignable_minutes=minutes,
            active_wip=wip,
            explanation_codes=(
                RecommendationCode.ACTIVE_ACCOUNT,
                RecommendationCode.SINGLE_HOME,
                RecommendationCode.DELIVERY_CAPABILITY,
                RecommendationCode.VERIFIED_COMPETENCY,
                RecommendationCode.CAPACITY_AVAILABLE,
                RecommendationCode.DEADLINE_FEASIBLE,
                RecommendationCode.LOWER_WIP,
                RecommendationCode.DETERMINISTIC_ORDER,
            ),
        )
        for index, (unit_id, user_id, minutes, wip, _) in enumerate(eligible, start=1)
    )
    hashes = {user_id: hashed for _, user_id, _, _, hashed in eligible}
    returned = candidates[:MAX_RETURNED_CANDIDATES]
    returned_ids = {candidate.analyst_user_id for candidate in returned}
    return (
        returned,
        exclusion_pairs(exclusions),
        {user_id: value for user_id, value in hashes.items() if user_id in returned_ids},
    )


def _candidate(
    row: RowMapping,
    demand: AssignmentDemand,
    team_caps: dict[UUID, int],
    person_caps: dict[UUID, int],
    required: int,
    forecast: CapacityForecast | None,
) -> tuple[UUID, UUID, int, int, str] | _InternalExclusion:
    unit_id, user_id = UUID(str(row["unit_id"])), UUID(str(row["user_id"]))
    if not row["is_active"] or active_analyst_role() not in (row["roles"] or ()):
        return _InternalExclusion.ACCOUNT
    if not row["assignment_eligible"] or int(row["home_count"]) != 1:
        return _InternalExclusion.POSTING
    if team_caps.get(unit_id, 0) != required:
        return _InternalExclusion.CAPABILITY
    if person_caps.get(user_id, 0) != required:
        return _InternalExclusion.COMPETENCY
    if int(row["active_wip"]) >= int(row["wip_limit"]):
        return _InternalExclusion.WIP
    if forecast is None:
        return _InternalExclusion.UNKNOWN
    assignable = forecast.assignable_minutes
    if assignable < demand.effort_max_minutes:
        return _InternalExclusion.CAPACITY
    wip = int(row["active_wip"])
    hashed = evidence_hash(
        {
            "account": row["source_hash"],
            "assignable": assignable,
            "membership_version": int(row["membership_version"]),
            "unit": str(unit_id),
            "user": str(user_id),
            "wip": wip,
        }
    )
    return unit_id, user_id, assignable, wip, hashed


class _InternalExclusion(StrEnum):
    ACCOUNT = "account"
    POSTING = "posting"
    CAPABILITY = "capability"
    COMPETENCY = "competency"
    WIP = "wip"
    UNKNOWN = "unknown"
    CAPACITY = "capacity"


def _safe_code(value: _InternalExclusion) -> ExclusionCode:
    if value is _InternalExclusion.UNKNOWN:
        return ExclusionCode.DATA_UNKNOWN
    if value is _InternalExclusion.CAPACITY:
        return ExclusionCode.CAPACITY_UNAVAILABLE
    return ExclusionCode.NOT_CURRENTLY_ELIGIBLE
