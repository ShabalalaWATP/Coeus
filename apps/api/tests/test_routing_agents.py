from dataclasses import replace
from uuid import uuid4

import pytest

from coeus.core.errors import AppError
from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.services.capability_catalogue import CapabilityCatalogue
from coeus.services.routing_agents import CmCapabilityAgent, RfaCapabilityAgent
from coeus.services.routing_records import ensure_jioc_state, latest_recommendation


def _ticket(intake: IntakeDetails) -> TicketRecord:
    return TicketRecord(
        ticket_id=uuid4(),
        reference="RFI-TEST-0001",
        requester_user_id=uuid4(),
        state=TicketState.JIOC_REVIEW,
        intake=intake,
    )


def _cm_agent() -> CmCapabilityAgent:
    return CmCapabilityAgent(CapabilityCatalogue())


def _rfa_agent() -> RfaCapabilityAgent:
    return RfaCapabilityAgent(CapabilityCatalogue())


def _complete_intake(**overrides: str | None) -> IntakeDetails:
    values: dict[str, str | None] = {
        "title": "Mock Exercise Summary",
        "description": "General mock overview for the exercise.",
        "operational_question": "What matters for the mock exercise?",
        "area_or_region": "Mock Region",
        "priority": "routine",
        "required_output_format": "Report",
        "customer_success_criteria": "Give the duty officer a clear picture.",
        "deadline": None,
        "known_context": None,
        "restrictions_or_caveats": None,
        "suggested_acg_context": None,
        "time_period_end": None,
        "time_period_start": None,
    }
    values.update(overrides)
    return IntakeDetails(
        title=values["title"],
        description=values["description"],
        operational_question=values["operational_question"],
        area_or_region=values["area_or_region"],
        priority=values["priority"],
        deadline=values["deadline"],
        required_output_format=values["required_output_format"],
        known_context=values["known_context"],
        restrictions_or_caveats=values["restrictions_or_caveats"],
        customer_success_criteria=values["customer_success_criteria"],
        suggested_acg_context=values["suggested_acg_context"],
        time_period_end=values["time_period_end"],
        time_period_start=values["time_period_start"],
    )


def test_cm_agent_confirms_collection_terms_even_without_a_team_keyword() -> None:
    intake = _complete_intake(description="Monitor the mock area daily.")

    review = _cm_agent().review(_ticket(intake))

    assert review.can_satisfy is True
    assert review.confidence == 1.0
    assert review.suggested_collection_team_name == "Collection Coordination Triage Cell"


def test_cm_agent_treats_team_keyword_only_match_as_unconfirmed_signal() -> None:
    intake = _complete_intake(description="Summarise mock shipping registry entries.")

    review = _cm_agent().review(_ticket(intake))

    assert review.can_satisfy is False
    assert review.confidence == 0.5
    assert "no confirmed collection signal" in review.reasoning_summary


def test_agents_report_no_signal_for_unrelated_intake() -> None:
    intake = _complete_intake(
        description="General mock overview for the exercise.",
        required_output_format="Summary",
    )
    ticket = _ticket(intake)

    rfa = _rfa_agent().review(ticket)
    cm = _cm_agent().review(ticket)

    assert rfa.can_satisfy is False
    assert rfa.confidence == 0.0
    assert rfa.reasoning_summary == "No strong assessment signal was found in the intake."
    assert cm.can_satisfy is False
    assert cm.confidence == 0.0
    assert cm.reasoning_summary == "No strong collection signal was found in the intake."


def test_cm_agent_requires_deadline_for_critical_priority_and_flags_risks() -> None:
    intake = _complete_intake(
        description="Monitor the mock area daily.",
        priority="critical",
        restrictions_or_caveats="Mock data only.",
    )

    review = _cm_agent().review(_ticket(intake))

    assert review.can_satisfy is False
    assert review.confidence == 0.0
    assert "Provide the deadline for critical priority routing." in (review.required_clarifications)
    assert review.reasoning_summary == (
        "Collection signal exists but clarifications are required before approval."
    )
    assert "Requester restrictions require manager review." in review.risks


def test_negated_route_language_is_not_treated_as_positive_intent() -> None:
    ticket = _ticket(
        _complete_intake(
            description="Assess existing reports without new collection.",
            required_output_format="assessment report",
        )
    )

    rfa = _rfa_agent().review(ticket)
    cm = _cm_agent().review(ticket)

    assert rfa.can_satisfy is True
    assert cm.can_satisfy is False
    assert "Negated routing language requires manager review." in rfa.risks
    assert "Negated routing language requires manager review." in cm.risks


def test_terms_match_through_punctuation_and_plurals() -> None:
    intake = _complete_intake(description="Can the team deploy more sensors?")

    review = _cm_agent().review(_ticket(intake))

    assert review.can_satisfy is True
    assert "mock sensor reporting" in review.suggested_collection_sources


@pytest.mark.parametrize(
    ("description", "agent"),
    (
        ("An assessment is not required.", "rfa"),
        ("Collection is not needed.", "cm"),
        ("Collection isn't needed.", "cm"),
        ("Collection isn\u2019t needed.", "cm"),
        ("Analysis? No.", "rfa"),
    ),
)
def test_postpositive_and_contracted_negation_is_never_positive_intent(
    description: str, agent: str
) -> None:
    intake = _complete_intake(
        title="Synthetic requirement",
        description=description,
        operational_question="What is needed?",
        required_output_format="Summary",
    )

    review = (_rfa_agent() if agent == "rfa" else _cm_agent()).review(_ticket(intake))

    assert review.can_satisfy is False
    assert "Negated routing language requires manager review." in review.risks


def test_negation_does_not_cross_clause_boundaries_and_analysis_is_not_pluralised() -> None:
    intake = _complete_intake(
        title="Synthetic requirement",
        description="Collection is not needed, but analysis is required.",
        operational_question="What is needed?",
        required_output_format="Summary",
    )

    rfa = _rfa_agent().review(_ticket(intake))
    cm = _cm_agent().review(_ticket(intake))

    assert rfa.can_satisfy is True
    assert cm.can_satisfy is False
    assert "Negated routing language requires manager review." in rfa.risks


def test_routing_record_guards_reject_missing_or_wrong_queue_state() -> None:
    ticket = _ticket(_complete_intake())
    drafted = replace(ticket, state=TicketState.DRAFT_INTAKE)

    with pytest.raises(AppError, match="Run capability reviews first"):
        latest_recommendation(ticket)
    with pytest.raises(AppError, match="not awaiting a JIOC decision"):
        ensure_jioc_state(drafted)
