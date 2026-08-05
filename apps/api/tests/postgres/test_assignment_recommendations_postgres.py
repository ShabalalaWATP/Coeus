"""Real PostgreSQL acceptance and rollback proof for assignment recommendations."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

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
    AcceptRecommendationRequest,
    AssignmentRecommendationConflict,
    AssignmentRecommendationDenied,
)
from coeus.persistence.assignment_recommendations_postgres import (
    PostgresAssignmentRecommendationStore,
)
from coeus.persistence.state_store import PostgresStateStore
from coeus.persistence.workflow_transaction import PostgresWorkflowTransaction
from coeus.repositories.tickets import InMemoryTicketRepository

pytestmark = pytest.mark.postgres


def test_preview_persists_versioned_demand_team_hold_and_deterministic_ranking(
    postgres_database_url: str,
) -> None:
    evidence = recommendation_evidence(postgres_database_url)
    first = prepare(evidence)
    second = prepare(evidence)

    assert first.estimate_version == 1
    assert second.estimate_version == 2
    assert tuple(item.analyst_user_id for item in first.candidates) == evidence.analyst_ids
    assert first.candidates[0].rank == 1
    assert all(item.assignable_minutes >= 240 for item in first.candidates)
    with evidence.engine.connect() as connection:
        estimates = connection.execute(
            text("SELECT count(*) FROM assignment_demand_estimates")
        ).scalar_one()
        holds = tuple(
            connection.execute(
                text(
                    "SELECT unit_id,held_minutes,state FROM assignment_demand_holds "
                    "ORDER BY hold_id"
                )
            )
        )
    assert estimates == 2
    assert len(holds) == 2
    assert all(row.unit_id == evidence.unit_id and row.held_minutes == 240 for row in holds)
    evidence.engine.dispose()


def test_accept_commits_ticket_ownership_package_reservation_and_decision_atomically(
    postgres_database_url: str,
) -> None:
    evidence = recommendation_evidence(postgres_database_url)
    preview = prepare(evidence)
    analyst_id = preview.recommended.analyst_user_id
    updated, ownership = accepted_ticket(evidence, analyst_id)

    assert PostgresWorkflowTransaction(postgres_database_url).commit_ticket_assignment(
        evidence.ticket,
        updated,
        assignment_audit(evidence),
        ownership,
        acceptance(preview, evidence.actor_id, evidence.unit_id, analyst_id),
    )

    with evidence.engine.connect() as connection:
        state = connection.execute(
            text(
                "SELECT recommendation.state,hold.state,decision.decision_type,decision.reason "
                "FROM assignment_recommendations recommendation "
                "JOIN assignment_demand_holds hold USING (recommendation_id) "
                "JOIN assignment_recommendation_decisions decision USING (recommendation_id)"
            )
        ).one()
        package = connection.execute(
            text(
                "SELECT state,estimated_minutes,remaining_minutes,due_at,version "
                "FROM canonical_work_packages"
            )
        ).one()
        reservation = connection.execute(
            text("SELECT user_id,reserved_minutes,state FROM capacity_reservations")
        ).one()
        ownership_count = connection.execute(
            text("SELECT count(*) FROM team_task_ownership WHERE state='active'")
        ).scalar_one()
    assert tuple(state) == ("accepted", "consumed", "accepted", "")
    assert package.state == "ready" and package.estimated_minutes == 240
    assert package.remaining_minutes == 240 and package.version == 2
    assert reservation.user_id == analyst_id and reservation.reserved_minutes == 240
    assert reservation.state == "active" and ownership_count == 1
    evidence.engine.dispose()


def test_reasoned_soft_override_can_select_only_another_hard_eligible_candidate(
    postgres_database_url: str,
) -> None:
    evidence = recommendation_evidence(postgres_database_url)
    preview = prepare(evidence)
    selected = preview.candidates[1].analyst_user_id
    updated, ownership = accepted_ticket(evidence, selected)
    reason = "The second analyst owns the related synthetic assessment."

    assert PostgresWorkflowTransaction(postgres_database_url).commit_ticket_assignment(
        evidence.ticket,
        updated,
        assignment_audit(evidence),
        ownership,
        acceptance(preview, evidence.actor_id, evidence.unit_id, selected, reason),
    )
    with evidence.engine.connect() as connection:
        decision = connection.execute(
            text(
                "SELECT selected_analyst_user_id,decision_type,reason "
                "FROM assignment_recommendation_decisions"
            )
        ).one()
    assert tuple(decision) == (selected, "soft_override", reason)
    evidence.engine.dispose()


def test_suspension_after_preview_rolls_back_every_assignment_write(
    postgres_database_url: str,
) -> None:
    evidence = recommendation_evidence(postgres_database_url)
    preview = prepare(evidence)
    analyst_id = preview.recommended.analyst_user_id
    updated, ownership = accepted_ticket(evidence, analyst_id)
    with evidence.engine.begin() as connection:
        connection.execute(
            text("UPDATE identity_account_projection SET is_active=false WHERE user_id=:user_id"),
            {"user_id": analyst_id},
        )

    with pytest.raises(AssignmentRecommendationDenied, match="eligible"):
        PostgresWorkflowTransaction(postgres_database_url).commit_ticket_assignment(
            evidence.ticket,
            updated,
            assignment_audit(evidence),
            ownership,
            acceptance(preview, evidence.actor_id, evidence.unit_id, analyst_id),
        )

    repository = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    assert repository.get(evidence.ticket.ticket_id) == evidence.ticket
    with evidence.engine.connect() as connection:
        counts = tuple(
            connection.execute(
                text(
                    "SELECT (SELECT count(*) FROM team_task_ownership),"
                    "(SELECT count(*) FROM canonical_work_packages),"
                    "(SELECT count(*) FROM capacity_reservations),"
                    "(SELECT count(*) FROM assignment_recommendation_decisions)"
                )
            ).one()
        )
        recommendation_state = connection.execute(
            text("SELECT state FROM assignment_recommendations")
        ).scalar_one()
    assert counts == (0, 0, 0, 0)
    assert recommendation_state == "prepared"
    evidence.engine.dispose()


def test_expired_preview_cannot_be_preaccepted(postgres_database_url: str) -> None:
    evidence = recommendation_evidence(postgres_database_url)
    preview = prepare(evidence)
    past_created = datetime.now(UTC) - timedelta(hours=2)
    past_expiry = datetime.now(UTC) - timedelta(hours=1)
    with evidence.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE assignment_recommendations SET created_at=:created,expires_at=:expiry "
                "WHERE recommendation_id=:recommendation_id"
            ),
            {
                "created": past_created,
                "expiry": past_expiry,
                "recommendation_id": preview.recommendation_id,
            },
        )
    request = AcceptRecommendationRequest(
        preview.recommendation_id,
        preview.preview_hash,
        evidence.unit_id,
        preview.recommended.analyst_user_id,
    )
    with pytest.raises(AssignmentRecommendationConflict, match="current"):
        PostgresAssignmentRecommendationStore(evidence.engine).acceptance(
            evidence.actor_id, request
        )
    evidence.engine.dispose()


def test_concurrent_acceptance_commits_exactly_one_assignment(postgres_database_url: str) -> None:
    evidence = recommendation_evidence(postgres_database_url)
    previews = (prepare(evidence), prepare(evidence))
    proposals = tuple(
        accepted_ticket(evidence, preview.recommended.analyst_user_id) for preview in previews
    )

    def commit(index: int) -> bool:
        preview = previews[index]
        updated, ownership = proposals[index]
        return PostgresWorkflowTransaction(postgres_database_url).commit_ticket_assignment(
            evidence.ticket,
            updated,
            assignment_audit(evidence),
            ownership,
            acceptance(
                preview,
                evidence.actor_id,
                evidence.unit_id,
                preview.recommended.analyst_user_id,
            ),
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(commit, (0, 1)))

    assert sorted(results) == [False, True]
    with evidence.engine.connect() as connection:
        counts = tuple(
            connection.execute(
                text(
                    "SELECT (SELECT count(*) FROM assignment_recommendation_decisions),"
                    "(SELECT count(*) FROM capacity_reservations),"
                    "(SELECT count(*) FROM team_task_ownership)"
                )
            ).one()
        )
    assert counts == (1, 1, 1)
    evidence.engine.dispose()
