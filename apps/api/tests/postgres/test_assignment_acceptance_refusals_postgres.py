"""Bindings re-checked inside the transaction that accepts a recommendation."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from assignment_recommendation_support import (
    acceptance,
    accepted_ticket,
    assignment_audit,
    prepare,
    recommendation_evidence,
)
from sqlalchemy import text

from coeus.domain.assignment_recommendations import (
    AssignmentRecommendationConflict,
    AssignmentRecommendationDenied,
)
from coeus.persistence.workflow_transaction import PostgresWorkflowTransaction

pytestmark = pytest.mark.postgres


def _commit(evidence, updated, ownership, accept) -> bool:  # type: ignore[no-untyped-def]
    return PostgresWorkflowTransaction(
        evidence.engine.url.render_as_string(hide_password=False)
    ).commit_ticket_assignment(
        evidence.ticket, updated, assignment_audit(evidence), ownership, accept
    )


def test_an_unknown_recommendation_cannot_be_accepted(postgres_database_url: str) -> None:
    evidence = recommendation_evidence(postgres_database_url)
    preview = prepare(evidence)
    analyst = preview.candidates[0].analyst_user_id
    updated, ownership = accepted_ticket(evidence, analyst)
    accept = replace(
        acceptance(preview, evidence.actor_id, evidence.unit_id, analyst),
        recommendation_id=uuid4(),
    )

    with pytest.raises(AssignmentRecommendationConflict, match="is unavailable"):
        _commit(evidence, updated, ownership, accept)
    evidence.engine.dispose()


def test_a_lapsed_hold_cannot_be_accepted(postgres_database_url: str) -> None:
    evidence = recommendation_evidence(postgres_database_url)
    preview = prepare(evidence)
    analyst = preview.candidates[0].analyst_user_id
    updated, ownership = accepted_ticket(evidence, analyst)
    lapsed = datetime.now(UTC) - timedelta(minutes=1)
    with evidence.engine.begin() as connection:
        connection.execute(
            text("UPDATE assignment_demand_holds SET created_at=:before,expires_at=:then"),
            {"before": lapsed - timedelta(minutes=15), "then": lapsed},
        )

    with pytest.raises(AssignmentRecommendationConflict, match="no longer current"):
        _commit(
            evidence,
            updated,
            ownership,
            acceptance(preview, evidence.actor_id, evidence.unit_id, analyst),
        )
    evidence.engine.dispose()


def test_an_actor_who_did_not_review_the_recommendation_cannot_accept_it(
    postgres_database_url: str,
) -> None:
    evidence = recommendation_evidence(postgres_database_url)
    preview = prepare(evidence)
    analyst = preview.candidates[0].analyst_user_id
    updated, ownership = accepted_ticket(evidence, analyst)

    with pytest.raises(AssignmentRecommendationConflict, match="no longer current"):
        _commit(
            evidence,
            updated,
            ownership,
            acceptance(preview, uuid4(), evidence.unit_id, analyst),
        )
    evidence.engine.dispose()


def test_a_candidate_who_became_ineligible_is_refused_at_acceptance(
    postgres_database_url: str,
) -> None:
    evidence = recommendation_evidence(postgres_database_url)
    preview = prepare(evidence)
    analyst = preview.candidates[0].analyst_user_id
    updated, ownership = accepted_ticket(evidence, analyst)
    with evidence.engine.begin() as connection:
        connection.execute(
            text("UPDATE identity_account_projection SET is_active=false WHERE user_id=:user"),
            {"user": analyst},
        )

    with pytest.raises(AssignmentRecommendationDenied, match="no longer eligible"):
        _commit(
            evidence,
            updated,
            ownership,
            acceptance(preview, evidence.actor_id, evidence.unit_id, analyst),
        )
    evidence.engine.dispose()


def test_an_override_reason_must_match_the_selected_candidate(
    postgres_database_url: str,
) -> None:
    evidence = recommendation_evidence(postgres_database_url)
    preview = prepare(evidence)
    recommended = preview.candidates[0].analyst_user_id
    updated, ownership = accepted_ticket(evidence, recommended)

    with pytest.raises(AssignmentRecommendationDenied, match="requires another candidate"):
        _commit(
            evidence,
            updated,
            ownership,
            acceptance(
                preview,
                evidence.actor_id,
                evidence.unit_id,
                recommended,
                "The second analyst owns the related synthetic assessment.",
            ),
        )
    evidence.engine.dispose()


def test_a_soft_override_without_a_reason_is_refused(postgres_database_url: str) -> None:
    evidence = recommendation_evidence(postgres_database_url)
    preview = prepare(evidence)
    alternative = preview.candidates[1].analyst_user_id
    updated, ownership = accepted_ticket(evidence, alternative)

    with pytest.raises(AssignmentRecommendationDenied, match="requires a reason"):
        _commit(
            evidence,
            updated,
            ownership,
            acceptance(preview, evidence.actor_id, evidence.unit_id, alternative),
        )
    evidence.engine.dispose()
