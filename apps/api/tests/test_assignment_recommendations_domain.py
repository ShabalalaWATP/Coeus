"""Domain invariants for bounded assignment demand and manager decisions."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from coeus.domain.assignment_recommendations import (
    AcceptRecommendationRequest,
    AssignmentDemand,
    PrepareRecommendationRequest,
    demand_hash,
)
from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.schemas.assignment_recommendations import (
    AssignmentRecommendationAcceptRequest,
    AssignmentRecommendationPreviewRequest,
)


def _demand() -> AssignmentDemand:
    start = datetime(2026, 8, 5, 9, tzinfo=UTC)
    return AssignmentDemand(
        uuid4(), WorkflowLeg.RFA, 120, 240, start, start + timedelta(days=2), ("RFA-A",)
    )


def test_demand_requires_bounded_quarter_hours_and_unique_capabilities() -> None:
    demand = _demand()
    with pytest.raises(ValueError, match="15-minute"):
        AssignmentDemand(
            demand.ticket_id,
            demand.workflow_leg,
            121,
            240,
            demand.window_start,
            demand.deadline,
            demand.capability_ids,
        )
    with pytest.raises(ValueError, match="unique"):
        AssignmentDemand(
            demand.ticket_id,
            demand.workflow_leg,
            120,
            240,
            demand.window_start,
            demand.deadline,
            ("RFA-A", "RFA-A"),
        )


def test_soft_override_reason_is_bounded() -> None:
    with pytest.raises(ValueError, match="10 to 500"):
        AcceptRecommendationRequest(uuid4(), "a" * 64, uuid4(), uuid4(), "short")


def test_demand_hash_is_actor_and_scope_bound_and_deterministic() -> None:
    actor, unit = uuid4(), uuid4()
    request = PrepareRecommendationRequest(_demand(), unit)
    assert demand_hash(actor, request) == demand_hash(actor, request)
    assert demand_hash(uuid4(), request) != demand_hash(actor, request)
    assert demand_hash(actor, PrepareRecommendationRequest(request.demand, None)) != demand_hash(
        actor, request
    )


def test_api_contract_rejects_invalid_effort_ranges() -> None:
    base = {
        "deadline": datetime.now(UTC) + timedelta(days=1),
        "capabilityIds": ["RFA-A"],
    }
    with pytest.raises(ValueError):
        AssignmentRecommendationPreviewRequest.model_validate(
            {**base, "effortMinMinutes": 31, "effortMaxMinutes": 60}
        )
    with pytest.raises(ValueError):
        AssignmentRecommendationPreviewRequest.model_validate(
            {**base, "effortMinMinutes": 75, "effortMaxMinutes": 60}
        )


def test_api_contract_rejects_short_override_reason() -> None:
    with pytest.raises(ValueError):
        AssignmentRecommendationAcceptRequest.model_validate(
            {
                "recommendationId": uuid4(),
                "previewHash": "a" * 64,
                "selectedUnitId": uuid4(),
                "selectedAnalystUserId": uuid4(),
                "overrideReason": "too short",
            }
        )
