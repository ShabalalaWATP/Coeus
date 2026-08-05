"""Bounds for large assignment evaluation and small human review lists."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from coeus.domain.assignment_recommendations import AssignmentDemand
from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.persistence import assignment_recommendation_ranking as ranking
from coeus.persistence.assignment_recommendation_queries import _ROSTER


def _demand() -> AssignmentDemand:
    start = datetime(2026, 8, 4, tzinfo=UTC)
    return AssignmentDemand(
        UUID(int=1),
        WorkflowLeg.RFA,
        60,
        120,
        start,
        start + timedelta(days=7),
        ("regional-analysis",),
    )


def _roster(size: int) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "unit_id": UUID(int=10 + index % 5),
            "user_id": UUID(int=1_000 + index),
        }
        for index in range(size)
    )


def _eligible(
    row: dict[str, object],
    _demand: AssignmentDemand,
    _team: dict[UUID, int],
    _people: dict[UUID, int],
    _required: int,
    _forecast: object,
) -> tuple[UUID, UUID, int, int, str]:
    user_id = row["user_id"]
    assert isinstance(user_id, UUID)
    unit_id = row["unit_id"]
    assert isinstance(unit_id, UUID)
    return unit_id, user_id, 1_000, user_id.int % 7, f"evidence-{user_id}"


def _patch_evidence(monkeypatch: pytest.MonkeyPatch, size: int) -> None:
    monkeypatch.setattr(ranking, "roster_rows", lambda *_args: _roster(size))
    monkeypatch.setattr(ranking, "capability_counts", lambda *_args: ({}, {}))
    monkeypatch.setattr(ranking, "active_team_hold_minutes", lambda *_args: 0)
    monkeypatch.setattr(ranking, "batch_person_forecasts", lambda *_args: {})
    monkeypatch.setattr(ranking, "_candidate", _eligible)


def test_evaluates_500_candidates_but_returns_only_top_10(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_evidence(monkeypatch, 500)

    candidates, exclusions, evidence = ranking.rank_candidates(
        SimpleNamespace(), (UUID(int=10),), _demand(), datetime(2026, 8, 4, tzinfo=UTC)
    )

    assert len(candidates) == 10
    assert tuple(candidate.rank for candidate in candidates) == tuple(range(1, 11))
    assert len(evidence) == 10
    assert not exclusions
    assert "LIMIT 501" in _ROSTER


def test_rejects_a_501_candidate_cohort(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_evidence(monkeypatch, 501)

    with pytest.raises(RuntimeError, match="cohort is too large"):
        ranking.rank_candidates(
            SimpleNamespace(), (UUID(int=10),), _demand(), datetime(2026, 8, 4, tzinfo=UTC)
        )
