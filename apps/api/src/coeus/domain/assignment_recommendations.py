"""Versioned demand estimates and human-approved assignment recommendations."""

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from uuid import UUID

from coeus.domain.team_task_ownership import WorkflowLeg


class AssignmentRecommendationDenied(PermissionError):
    """Current scoped assignment authority or eligibility is absent."""


class AssignmentRecommendationConflict(ValueError):
    """Preview evidence changed or a command identity was reused."""


class RecommendationCode(StrEnum):
    ACTIVE_ACCOUNT = "active_account"
    SINGLE_HOME = "single_home_posting"
    DELIVERY_CAPABILITY = "delivery_capability"
    VERIFIED_COMPETENCY = "verified_competency"
    CAPACITY_AVAILABLE = "capacity_available"
    DEADLINE_FEASIBLE = "deadline_feasible"
    LOWER_WIP = "lower_work_in_progress"
    DETERMINISTIC_ORDER = "deterministic_order"


class ExclusionCode(StrEnum):
    NOT_CURRENTLY_ELIGIBLE = "not_currently_eligible"
    CAPACITY_UNAVAILABLE = "capacity_unavailable"
    DATA_UNKNOWN = "data_unknown"


@dataclass(frozen=True)
class AssignmentDemand:
    ticket_id: UUID
    workflow_leg: WorkflowLeg
    effort_min_minutes: int
    effort_max_minutes: int
    window_start: datetime
    deadline: datetime
    capability_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.window_start.tzinfo is None or self.deadline.tzinfo is None:
            raise ValueError("assignment demand bounds must be timezone-aware")
        if self.window_start >= self.deadline:
            raise ValueError("assignment demand deadline must follow its start")
        if (
            self.effort_min_minutes <= 0
            or self.effort_max_minutes < self.effort_min_minutes
            or self.effort_min_minutes % 15
            or self.effort_max_minutes % 15
        ):
            raise ValueError("assignment demand must use bounded 15-minute increments")
        if not self.capability_ids or len(self.capability_ids) > 12:
            raise ValueError("assignment demand requires one to twelve capabilities")
        normalised = tuple(value.strip() for value in self.capability_ids)
        if any(not value or len(value) > 120 for value in normalised):
            raise ValueError("assignment capability identity is invalid")
        if len(set(normalised)) != len(normalised):
            raise ValueError("assignment capabilities must be unique")


@dataclass(frozen=True)
class RankedAssignmentCandidate:
    unit_id: UUID
    analyst_user_id: UUID
    rank: int
    assignable_minutes: int
    active_wip: int
    explanation_codes: tuple[RecommendationCode, ...]


@dataclass(frozen=True)
class AssignmentRecommendationPreview:
    recommendation_id: UUID
    estimate_id: UUID
    estimate_version: int
    hold_id: UUID
    preview_hash: str
    expires_at: datetime
    candidates: tuple[RankedAssignmentCandidate, ...]
    exclusion_counts: tuple[tuple[ExclusionCode, int], ...]

    @property
    def recommended(self) -> RankedAssignmentCandidate:
        if not self.candidates:
            raise AssignmentRecommendationDenied("no eligible assignment candidate is available")
        return self.candidates[0]


@dataclass(frozen=True)
class PrepareRecommendationRequest:
    demand: AssignmentDemand
    unit_id: UUID | None


@dataclass(frozen=True)
class AcceptRecommendationRequest:
    recommendation_id: UUID
    preview_hash: str
    selected_unit_id: UUID
    selected_analyst_user_id: UUID
    override_reason: str = ""

    def __post_init__(self) -> None:
        if len(self.preview_hash) != 64:
            raise ValueError("assignment recommendation hash is invalid")
        reason = self.override_reason.strip()
        if reason and not 10 <= len(reason) <= 500:
            raise ValueError("assignment override reason must contain 10 to 500 characters")


@dataclass(frozen=True)
class AssignmentRecommendationAcceptance:
    recommendation_id: UUID
    preview_hash: str
    actor_user_id: UUID
    selected_unit_id: UUID
    selected_analyst_user_id: UUID
    override_reason: str


def demand_hash(actor_user_id: UUID, request: PrepareRecommendationRequest) -> str:
    demand = request.demand
    value = {
        "actor": str(actor_user_id),
        "capabilities": list(demand.capability_ids),
        "deadline": demand.deadline.isoformat(),
        "effort_max": demand.effort_max_minutes,
        "effort_min": demand.effort_min_minutes,
        "leg": demand.workflow_leg.value,
        "start": demand.window_start.isoformat(),
        "ticket": str(demand.ticket_id),
        "unit": str(request.unit_id) if request.unit_id else None,
    }
    return sha256(json.dumps(value, separators=(",", ":"), sort_keys=True).encode()).hexdigest()
