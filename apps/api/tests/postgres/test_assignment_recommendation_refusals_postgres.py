"""Preparation and acceptance refusals for assignment recommendations."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from assignment_recommendation_support import prepare, recommendation_evidence
from sqlalchemy import text

from coeus.domain.assignment_recommendations import (
    AcceptRecommendationRequest,
    AssignmentRecommendationConflict,
    AssignmentRecommendationDenied,
    PrepareRecommendationRequest,
)
from coeus.persistence.assignment_recommendations_postgres import (
    PostgresAssignmentRecommendationStore,
)

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("minutes", [4, 31])
def test_a_hold_lifetime_outside_the_supported_range_is_refused(minutes: int) -> None:
    with pytest.raises(ValueError, match="between 5 and 30 minutes"):
        PostgresAssignmentRecommendationStore(object(), hold_minutes=minutes)  # type: ignore[arg-type]


def test_a_recommendation_for_an_unknown_ticket_is_refused(postgres_database_url: str) -> None:
    evidence = recommendation_evidence(postgres_database_url)
    request = PrepareRecommendationRequest(
        replace(evidence.demand, ticket_id=uuid4()), evidence.unit_id
    )

    with pytest.raises(AssignmentRecommendationDenied, match="ticket is unavailable"):
        PostgresAssignmentRecommendationStore(evidence.engine).prepare(evidence.actor_id, request)
    evidence.engine.dispose()


def test_an_actor_without_current_authority_gets_no_recommendation(
    postgres_database_url: str,
) -> None:
    evidence = recommendation_evidence(postgres_database_url)
    request = PrepareRecommendationRequest(evidence.demand, evidence.unit_id)

    with pytest.raises(AssignmentRecommendationDenied, match="no current assignment authority"):
        PostgresAssignmentRecommendationStore(evidence.engine).prepare(uuid4(), request)
    evidence.engine.dispose()


def test_a_cohort_with_no_eligible_person_is_refused(postgres_database_url: str) -> None:
    evidence = recommendation_evidence(postgres_database_url)
    with evidence.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE identity_account_projection SET is_active=false "
                "WHERE user_id=ANY(CAST(:analysts AS uuid[]))"
            ),
            {"analysts": list(evidence.analyst_ids)},
        )
    request = PrepareRecommendationRequest(evidence.demand, evidence.unit_id)

    with pytest.raises(AssignmentRecommendationDenied, match="no eligible assignment candidate"):
        PostgresAssignmentRecommendationStore(evidence.engine).prepare(evidence.actor_id, request)
    evidence.engine.dispose()


def test_a_lapsed_recommendation_is_expired_and_cannot_be_accepted(
    postgres_database_url: str,
) -> None:
    evidence = recommendation_evidence(postgres_database_url)
    store = PostgresAssignmentRecommendationStore(evidence.engine)
    preview = prepare(evidence)
    lapsed = datetime.now(UTC) - timedelta(minutes=1)
    with evidence.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE assignment_recommendations SET created_at=:before,expires_at=:then,"
                "updated_at=:before"
            ),
            {"before": lapsed - timedelta(minutes=15), "then": lapsed},
        )
        connection.execute(
            text("UPDATE assignment_demand_holds SET created_at=:before,expires_at=:then"),
            {"before": lapsed - timedelta(minutes=15), "then": lapsed},
        )

    with pytest.raises(AssignmentRecommendationConflict, match="is not current"):
        store.acceptance(
            evidence.actor_id,
            AcceptRecommendationRequest(
                preview.recommendation_id,
                preview.preview_hash,
                evidence.unit_id,
                preview.candidates[0].analyst_user_id,
            ),
        )

    # Preparing again sweeps the lapsed hold and recommendation.
    prepare(evidence)
    with evidence.engine.connect() as connection:
        states = tuple(
            connection.execute(
                text("SELECT state FROM assignment_recommendations ORDER BY created_at")
            ).scalars()
        )
        holds = tuple(
            connection.execute(
                text("SELECT state FROM assignment_demand_holds ORDER BY created_at")
            ).scalars()
        )
    assert states == ("expired", "prepared")
    assert holds == ("expired", "active")
    evidence.engine.dispose()


@pytest.mark.parametrize("field", ["recommendation_id", "preview_hash", "unit", "analyst"])
def test_acceptance_is_bound_to_the_exact_reviewed_candidate(
    postgres_database_url: str, field: str
) -> None:
    evidence = recommendation_evidence(postgres_database_url)
    store = PostgresAssignmentRecommendationStore(evidence.engine)
    preview = prepare(evidence)
    analyst = preview.candidates[0].analyst_user_id
    request = AcceptRecommendationRequest(
        uuid4() if field == "recommendation_id" else preview.recommendation_id,
        "b" * 64 if field == "preview_hash" else preview.preview_hash,
        uuid4() if field == "unit" else evidence.unit_id,
        uuid4() if field == "analyst" else analyst,
    )

    with pytest.raises(AssignmentRecommendationConflict, match="is not current"):
        store.acceptance(evidence.actor_id, request)
    evidence.engine.dispose()


def test_an_override_reason_must_match_whether_the_top_candidate_was_chosen(
    postgres_database_url: str,
) -> None:
    evidence = recommendation_evidence(postgres_database_url)
    store = PostgresAssignmentRecommendationStore(evidence.engine)
    preview = prepare(evidence)
    recommended = preview.candidates[0].analyst_user_id
    alternative = preview.candidates[1].analyst_user_id

    def request(analyst_id: object, reason: str) -> AcceptRecommendationRequest:
        return AcceptRecommendationRequest(
            preview.recommendation_id,
            preview.preview_hash,
            evidence.unit_id,
            analyst_id,  # type: ignore[arg-type]
            reason,
        )

    with pytest.raises(AssignmentRecommendationDenied, match="soft override requires a reason"):
        store.acceptance(evidence.actor_id, request(alternative, "   "))
    with pytest.raises(AssignmentRecommendationDenied, match="requires another candidate"):
        store.acceptance(
            evidence.actor_id, request(recommended, "The second analyst has the context.")
        )

    accepted = store.acceptance(evidence.actor_id, request(recommended, ""))
    overridden = store.acceptance(
        evidence.actor_id, request(alternative, "  The second analyst has the context.  ")
    )
    assert accepted.override_reason == ""
    assert overridden.override_reason == "The second analyst has the context."
    evidence.engine.dispose()
