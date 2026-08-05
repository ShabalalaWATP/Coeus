"""Transaction routing and refusal translation for assignment commits."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from coeus.core.errors import AppError
from coeus.domain.assignment_recommendations import (
    AssignmentRecommendationAcceptance,
    AssignmentRecommendationConflict,
    AssignmentRecommendationDenied,
)
from coeus.domain.enums import TicketState
from coeus.domain.team_task_ownership import AssignmentOwnershipIntent, WorkflowLeg
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.services.ticket_mutations import TicketMutationService

ACTOR = SimpleNamespace(user_id=uuid4())
UNIT = uuid4()


class _Transaction:
    def __init__(self, outcome: object = True) -> None:
        self._outcome = outcome
        self.calls: list[tuple[object, ...]] = []

    def commit_ticket_assignment(self, *args: object) -> bool:
        self.calls.append(args)
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return bool(self._outcome)


class _Repository:
    def __init__(self) -> None:
        self.saved: list[TicketRecord] = []

    def save_with_confirmation(self, ticket: TicketRecord, confirm: object) -> None:
        self.saved.append(ticket)
        confirm()  # type: ignore[operator]

    def save_if_current(self, expected: TicketRecord, proposed: TicketRecord) -> TicketRecord:
        self.saved.append(proposed)
        return proposed


def _ticket(state: TicketState = TicketState.ANALYST_ASSIGNMENT) -> TicketRecord:
    return TicketRecord(
        uuid4(), "TCK-0001", uuid4(), state, IntakeDetails(title="Synthetic ticket")
    )


def _acceptance() -> AssignmentRecommendationAcceptance:
    return AssignmentRecommendationAcceptance(uuid4(), "a" * 64, ACTOR.user_id, UNIT, uuid4(), "")


def _service(transaction: _Transaction | None) -> TicketMutationService:
    return TicketMutationService(
        _Repository(),  # type: ignore[arg-type]
        SimpleNamespace(record=lambda *_args: None),  # type: ignore[arg-type]
        transaction,  # type: ignore[arg-type]
    )


def _intent() -> AssignmentOwnershipIntent:
    return AssignmentOwnershipIntent(UNIT, WorkflowLeg.RFA, ACTOR.user_id, uuid4())


def _commit(
    service: TicketMutationService,
    recommendation: AssignmentRecommendationAcceptance | None = None,
) -> TicketRecord:
    expected = _ticket()
    return service.save_assignment_if_current(
        expected,
        expected,
        ACTOR,  # type: ignore[arg-type]
        "analyst_assigned",
        {},
        _intent(),
        recommendation,
    )


def test_a_plain_assignment_commits_through_the_transaction() -> None:
    transaction = _Transaction()

    committed = _commit(_service(transaction))

    assert committed.reference == "TCK-0001"
    # No acceptance is passed when there is no recommendation to bind.
    assert len(transaction.calls[0]) == 4


def test_an_accepted_recommendation_is_passed_to_the_transaction() -> None:
    transaction = _Transaction()
    acceptance = _acceptance()

    _commit(_service(transaction), acceptance)

    assert transaction.calls[0][4] is acceptance


def test_accepting_a_recommendation_without_a_transaction_fails_closed() -> None:
    with pytest.raises(AppError) as error:
        _commit(_service(None), _acceptance())

    assert error.value.status_code == 503
    assert error.value.code == "assignment_recommendation_unavailable"


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (AssignmentRecommendationConflict("stale"), "assignment_recommendation_changed"),
        (AssignmentRecommendationDenied("ineligible"), "assignment_candidate_ineligible"),
        (ValueError("delivery authority"), "assignment_team_authority_changed"),
    ],
)
def test_each_transactional_refusal_maps_to_its_own_conflict(failure: Exception, code: str) -> None:
    with pytest.raises(AppError) as error:
        _commit(_service(_Transaction(failure)), _acceptance())

    assert error.value.status_code == 409
    assert error.value.code == code
    assert str(failure) not in error.value.message


def test_a_ticket_that_moved_under_the_commit_is_reported_as_changed() -> None:
    with pytest.raises(AppError) as error:
        _commit(_service(_Transaction(False)))

    assert error.value.status_code == 409
    assert error.value.code == "ticket_changed"
