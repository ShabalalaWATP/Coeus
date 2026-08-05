"""Authority scoping and candidate labelling in the recommendation service."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from coeus.core.errors import AppError
from coeus.domain.assignment_recommendations import (
    AssignmentRecommendationPreview,
    RankedAssignmentCandidate,
    RecommendationCode,
)
from coeus.domain.enums import TicketState
from coeus.domain.tickets import (
    IntakeDetails,
    ManagerRoutingDecision,
    ManagerRoutingDecisionStatus,
    RoutingRoute,
    TicketRecord,
)
from coeus.services.assignment_recommendations import AssignmentRecommendationService

DEADLINE = datetime.now(UTC) + timedelta(days=3)
UNIT_A, UNIT_B = sorted((uuid4(), uuid4()), key=str)
FIRST, SECOND = uuid4(), uuid4()
ACTOR = SimpleNamespace(user_id=uuid4(), permissions=set())


class _Tickets:
    def __init__(self, ticket: TicketRecord) -> None:
        self.tickets = SimpleNamespace(get_workflow_ticket=lambda *_args: ticket)


class _Assignments:
    def __init__(self, teams: tuple[object, ...] = (), accounts: dict[UUID, str] | None = None):
        self._teams = teams
        self._accounts = accounts or {}
        self.requested: list[tuple[UUID, tuple[UUID, ...]]] = []

    def assignment_teams(self, *_args: object) -> tuple[object, ...]:
        return self._teams

    def assignment_team(self, *args: object) -> object:
        return args[2]

    def recommendation_candidate_accounts(self, *args: object) -> tuple[SimpleNamespace, ...]:
        unit_id, ids = args[2], args[3]
        self.requested.append((unit_id, ids))  # type: ignore[arg-type]
        return tuple(
            SimpleNamespace(user_id=value, display_name=self._accounts[value])
            for value in ids  # type: ignore[union-attr]
            if value in self._accounts
        )


class _Store:
    def __init__(self) -> None:
        self.request: object = None

    def prepare(self, _actor: UUID, request: object) -> object:
        self.request = request
        return request


def _decision() -> ManagerRoutingDecision:
    return ManagerRoutingDecision(
        uuid4(),
        uuid4(),
        RoutingRoute.RFA,
        ManagerRoutingDecisionStatus.APPROVED,
        "Approved for RFA.",
        None,
        uuid4(),
        datetime.now(UTC),
    )


def _ticket(**overrides: object) -> TicketRecord:
    values: dict[str, object] = {
        "ticket_id": uuid4(),
        "reference": "TCK-0001",
        "requester_user_id": uuid4(),
        "state": TicketState.ANALYST_ASSIGNMENT,
        "intake": IntakeDetails(title="Synthetic"),
        "manager_decisions": (_decision(),),
    }
    values.update(overrides)
    return TicketRecord(**values)  # type: ignore[arg-type]


def _service(
    assignments: _Assignments, ticket: TicketRecord | None = None
) -> tuple[AssignmentRecommendationService, _Store]:
    store = _Store()
    service = AssignmentRecommendationService(
        _Tickets(ticket or _ticket()),  # type: ignore[arg-type]
        assignments,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
    )
    return service, store


def _preview() -> AssignmentRecommendationPreview:
    return AssignmentRecommendationPreview(
        uuid4(),
        uuid4(),
        1,
        uuid4(),
        "a" * 64,
        DEADLINE,
        (
            RankedAssignmentCandidate(
                UNIT_B, SECOND, 2, 480, 0, (RecommendationCode.ACTIVE_ACCOUNT,)
            ),
            RankedAssignmentCandidate(
                UNIT_A, FIRST, 1, 480, 0, (RecommendationCode.ACTIVE_ACCOUNT,)
            ),
        ),
        (),
    )


def test_an_unscoped_preview_needs_at_least_one_managed_team() -> None:
    service, _ = _service(_Assignments(teams=()))

    with pytest.raises(AppError) as error:
        service.preview(ACTOR, uuid4(), 240, 480, DEADLINE, ("regional-analysis",), None)  # type: ignore[arg-type]

    assert error.value.status_code == 403


def test_an_unscoped_preview_with_a_managed_team_reaches_the_store() -> None:
    service, store = _service(_Assignments(teams=(object(),)))

    service.preview(ACTOR, uuid4(), 240, 480, DEADLINE, ("regional-analysis",), None)  # type: ignore[arg-type]

    assert store.request is not None
    assert store.request.unit_id is None  # type: ignore[attr-defined]


def test_display_names_are_resolved_one_authorised_team_at_a_time() -> None:
    assignments = _Assignments(accounts={FIRST: "Ada Lovelace", SECOND: "Grace Hopper"})
    service, _ = _service(assignments)

    names = service.candidate_display_names(ACTOR, uuid4(), _preview())  # type: ignore[arg-type]

    assert names == {FIRST: "Ada Lovelace", SECOND: "Grace Hopper"}
    # Teams are visited in a deterministic order, one lookup each.
    assert [unit for unit, _ in assignments.requested] == [UNIT_A, UNIT_B]
    assert [ids for _, ids in assignments.requested] == [(FIRST,), (SECOND,)]


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"state": TicketState.ANALYST_IN_PROGRESS}, "invalid_ticket_state"),
        ({"manager_decisions": ()}, "route_not_approved"),
    ],
)
def test_a_ticket_outside_the_assignment_step_is_refused(
    overrides: dict[str, object], code: str
) -> None:
    service, _ = _service(_Assignments(teams=(object(),)), _ticket(**overrides))

    with pytest.raises(AppError) as error:
        service.preview(ACTOR, uuid4(), 240, 480, DEADLINE, ("regional-analysis",), None)  # type: ignore[arg-type]

    assert error.value.code == code
