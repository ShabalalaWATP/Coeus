"""Bindings a reviewed recommendation must still satisfy when it is accepted."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from coeus.domain.assignment_recommendations import (
    AssignmentRecommendationAcceptance,
    AssignmentRecommendationConflict,
    AssignmentRecommendationDenied,
)
from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.persistence.assignment_recommendation_acceptance import _validate_bound_evidence

NOW = datetime(2026, 8, 4, 12, tzinfo=UTC)
TICKET, UNIT, ANALYST, ACTOR = uuid4(), uuid4(), uuid4(), uuid4()
PACKAGE_IDS = (uuid4(),)
HASH = "a" * 64


def _acceptance(**overrides: object) -> AssignmentRecommendationAcceptance:
    values: dict[str, object] = {
        "recommendation_id": uuid4(),
        "preview_hash": HASH,
        "actor_user_id": ACTOR,
        "selected_unit_id": UNIT,
        "selected_analyst_user_id": ANALYST,
        "override_reason": "",
    }
    values.update(overrides)
    return AssignmentRecommendationAcceptance(**values)  # type: ignore[arg-type]


def _row(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "state": "prepared",
        "hold_state": "active",
        "expires_at": NOW + timedelta(minutes=15),
        "hold_expires_at": NOW + timedelta(minutes=15),
        "actor_user_id": ACTOR,
        "preview_hash": HASH,
        "ticket_id": TICKET,
        "workflow_leg": WorkflowLeg.RFA.value,
        "ticket_version": 3,
        "selected_rank": 1,
        "selected_unit_id": UNIT,
        "effort_min_minutes": 60,
        "effort_max_minutes": 120,
        "window_start": NOW,
        "deadline": NOW + timedelta(days=7),
        "capability_ids": ["regional-analysis"],
    }
    values.update(overrides)
    return values


def _validate(
    row: dict[str, object],
    acceptance: AssignmentRecommendationAcceptance | None = None,
    package_ids: tuple[UUID, ...] = PACKAGE_IDS,
) -> object:
    return _validate_bound_evidence(
        row,  # type: ignore[arg-type]
        acceptance or _acceptance(),
        TICKET,
        WorkflowLeg.RFA,
        3,
        package_ids,
        NOW,
    )


def test_current_evidence_yields_the_reviewed_demand() -> None:
    demand = _validate(_row())

    assert demand.ticket_id == TICKET
    assert demand.workflow_leg is WorkflowLeg.RFA
    assert (demand.effort_min_minutes, demand.effort_max_minutes) == (60, 120)
    assert demand.capability_ids == ("regional-analysis",)


@pytest.mark.parametrize(
    "overrides",
    [
        {"state": "accepted"},
        {"hold_state": "expired"},
        {"expires_at": NOW},
        {"hold_expires_at": NOW},
        {"actor_user_id": uuid4()},
        {"preview_hash": "b" * 64},
        {"ticket_id": uuid4()},
        {"workflow_leg": WorkflowLeg.QC.value},
        {"ticket_version": 4},
    ],
)
def test_any_changed_binding_makes_the_recommendation_stale(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(AssignmentRecommendationConflict, match="no longer current"):
        _validate(_row(**overrides))


def test_a_recommendation_without_a_work_package_cannot_be_accepted() -> None:
    with pytest.raises(AssignmentRecommendationConflict, match="no longer current"):
        _validate(_row(), package_ids=())


@pytest.mark.parametrize(
    "overrides",
    [{"selected_rank": None}, {"selected_unit_id": uuid4()}],
)
def test_a_candidate_outside_the_reviewed_list_is_refused(overrides: dict[str, object]) -> None:
    with pytest.raises(AssignmentRecommendationDenied, match="not in the reviewed recommendation"):
        _validate(_row(**overrides))


def test_an_override_reason_is_validated_at_the_domain_boundary() -> None:
    assert _acceptance(override_reason="  ").override_reason == "  "
