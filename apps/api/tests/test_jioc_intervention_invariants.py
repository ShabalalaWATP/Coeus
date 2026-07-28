"""Intervention allowlists must stay aligned with the ticket state machine."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.enums import TicketState
from coeus.domain.jioc_intervention import JiocIntervention
from coeus.domain.state_machine import ALLOWED_TRANSITIONS
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.main import create_app
from coeus.services.jioc_intervention import (
    HOLDABLE_STATES,
    REVIEWABLE_STATES,
    JiocInterventionService,
)


def test_holdable_states_mirror_the_state_machine_hold_edges() -> None:
    resumable = ALLOWED_TRANSITIONS[TicketState.JIOC_INTERVENTION_HOLD] - {TicketState.CANCELLED}
    assert resumable == HOLDABLE_STATES
    for state in HOLDABLE_STATES:
        assert TicketState.JIOC_INTERVENTION_HOLD in ALLOWED_TRANSITIONS[state]


def test_reviewable_states_can_all_reach_jioc_review() -> None:
    for state in REVIEWABLE_STATES:
        assert TicketState.JIOC_REVIEW in ALLOWED_TRANSITIONS[state]


def _held_ticket(app, previous_state: str):
    ticket_id = uuid4()
    held = TicketRecord(
        ticket_id=ticket_id,
        reference=f"TCK-{uuid4().hex[:6].upper()}",
        requester_user_id=uuid4(),
        state=TicketState.JIOC_INTERVENTION_HOLD,
        intake=IntakeDetails(),
        jioc_interventions=(
            JiocIntervention(
                uuid4(),
                ticket_id,
                "hold",
                "Review pause.",
                previous_state,
                uuid4(),
                datetime.now(UTC),
            ),
        ),
    )
    app.state.ticket_services.tickets._repository.save(held)
    return held


def test_resume_rejects_a_corrupt_previous_state_cleanly() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    actor = app.state.access_services.repository.get_user_by_username("jioc.team@example.test")
    assert actor is not None
    service = JiocInterventionService(app.state.ticket_services)
    held = _held_ticket(app, "NOT_A_REAL_STATE")

    with pytest.raises(AppError) as corrupt:
        service.resume(actor, held.ticket_id, "Resume the held request.")

    assert corrupt.value.status_code == 409
    assert corrupt.value.code == "intervention_state_invalid"


def test_resume_still_accepts_legacy_previous_state_strings() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    actor = app.state.access_services.repository.get_user_by_username("jioc.team@example.test")
    assert actor is not None
    service = JiocInterventionService(app.state.ticket_services)
    held = _held_ticket(app, "ROUTE_ASSESSMENT")

    resumed = service.resume(actor, held.ticket_id, "Resume the held request.")

    assert resumed.state == TicketState.JIOC_REVIEW
