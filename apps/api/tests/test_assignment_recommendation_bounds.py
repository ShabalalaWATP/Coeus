"""Deadline bounding and candidate labelling for assignment recommendations."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from coeus.core.errors import AppError
from coeus.domain.assignment_recommendations import (
    AcceptRecommendationRequest,
    AssignmentDemand,
    AssignmentRecommendationDenied,
    AssignmentRecommendationPreview,
    ExclusionCode,
    RankedAssignmentCandidate,
    RecommendationCode,
)
from coeus.domain.enums import TicketState
from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.domain.tickets import IntakeDetails, RoutingRoute, TicketRecord
from coeus.services.assignment_recommendations import _bounded_deadline, _workflow_leg

REQUESTED = datetime(2026, 9, 1, 12, tzinfo=UTC)


def _ticket(deadline: str | None) -> TicketRecord:
    intake = None if deadline is None else IntakeDetails(title="Synthetic", deadline=deadline)
    return TicketRecord(uuid4(), "TCK-0001", uuid4(), TicketState.ANALYST_ASSIGNMENT, intake)


def test_a_ticket_with_no_intake_leaves_the_requested_deadline_alone() -> None:
    assert _bounded_deadline(_ticket(None), REQUESTED) == REQUESTED
    assert _bounded_deadline(_ticket(""), REQUESTED) == REQUESTED


def test_a_free_text_deadline_leaves_the_requested_deadline_alone() -> None:
    # Intake deadlines are free text, so "Friday" is common and must not
    # disable the whole recommendation.
    assert _bounded_deadline(_ticket("Friday"), REQUESTED) == REQUESTED


def test_an_earlier_customer_deadline_caps_the_request() -> None:
    bounded = _bounded_deadline(_ticket("2026-08-21"), REQUESTED)

    assert bounded == datetime(2026, 8, 21, 23, 59, 59, 999_999, tzinfo=UTC)


def test_a_later_customer_deadline_does_not_extend_the_request() -> None:
    assert _bounded_deadline(_ticket("2027-01-01"), REQUESTED) == REQUESTED


def test_an_aware_customer_deadline_is_compared_in_utc() -> None:
    bounded = _bounded_deadline(_ticket("2026-08-21T09:00:00+02:00"), REQUESTED)

    assert bounded == datetime(2026, 8, 21, 7, tzinfo=UTC)


def test_a_naive_requested_deadline_is_refused() -> None:
    with pytest.raises(AppError) as error:
        _bounded_deadline(_ticket(None), datetime(2026, 9, 1, 12))

    assert error.value.code == "invalid_deadline"


@pytest.mark.parametrize(
    ("route", "leg"),
    [
        (RoutingRoute.RFA, WorkflowLeg.RFA),
        (RoutingRoute.CM, WorkflowLeg.CM_COLLECTION),
    ],
)
def test_each_approved_route_maps_to_its_delivery_leg(
    route: RoutingRoute, leg: WorkflowLeg
) -> None:
    assert _workflow_leg(route) is leg


def _candidate(unit_id: UUID, analyst_id: UUID, rank: int) -> RankedAssignmentCandidate:
    return RankedAssignmentCandidate(
        unit_id, analyst_id, rank, 480, 0, (RecommendationCode.ACTIVE_ACCOUNT,)
    )


def test_a_preview_reports_its_top_candidate_and_refuses_an_empty_one() -> None:
    unit_id, analyst_id = uuid4(), uuid4()
    preview = AssignmentRecommendationPreview(
        uuid4(),
        uuid4(),
        1,
        uuid4(),
        "a" * 64,
        REQUESTED,
        (_candidate(unit_id, analyst_id, 1), _candidate(unit_id, uuid4(), 2)),
        ((ExclusionCode.DATA_UNKNOWN, 1),),
    )

    assert preview.recommended.analyst_user_id == analyst_id

    empty = SimpleNamespace(candidates=())
    with pytest.raises(AssignmentRecommendationDenied, match="no eligible assignment candidate"):
        AssignmentRecommendationPreview.recommended.fget(empty)  # type: ignore[attr-defined]


def _demand(**overrides: object) -> AssignmentDemand:
    values: dict[str, object] = {
        "ticket_id": uuid4(),
        "workflow_leg": WorkflowLeg.RFA,
        "effort_min_minutes": 60,
        "effort_max_minutes": 120,
        "window_start": REQUESTED,
        "deadline": datetime(2026, 9, 8, 12, tzinfo=UTC),
        "capability_ids": ("maritime-analysis",),
    }
    values.update(overrides)
    return AssignmentDemand(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "overrides",
    [
        {"window_start": datetime(2026, 9, 1, 12)},
        {"deadline": datetime(2026, 9, 8, 12)},
    ],
)
def test_assignment_demand_bounds_must_carry_a_time_zone(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="must be timezone-aware"):
        _demand(**overrides)


def test_an_assignment_demand_deadline_must_follow_its_start() -> None:
    with pytest.raises(ValueError, match="deadline must follow its start"):
        _demand(deadline=REQUESTED)


@pytest.mark.parametrize(
    "capability_ids",
    [(), tuple(f"capability-{index}" for index in range(13))],
)
def test_an_assignment_demand_needs_one_to_twelve_capabilities(
    capability_ids: tuple[str, ...],
) -> None:
    with pytest.raises(ValueError, match="one to twelve capabilities"):
        _demand(capability_ids=capability_ids)


@pytest.mark.parametrize("capability", ["   ", "c" * 121])
def test_a_blank_or_oversized_capability_identity_is_refused(capability: str) -> None:
    with pytest.raises(ValueError, match="capability identity is invalid"):
        _demand(capability_ids=(capability,))


def test_an_acceptance_needs_a_full_length_preview_hash() -> None:
    with pytest.raises(ValueError, match="recommendation hash is invalid"):
        AcceptRecommendationRequest(uuid4(), "a" * 63, uuid4(), uuid4())
