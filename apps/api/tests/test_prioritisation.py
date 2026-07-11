from datetime import UTC, datetime
from uuid import uuid4

import pytest

from coeus.domain.enums import TicketState
from coeus.domain.prioritisation import PriorityAssessment, assess_intake
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.persistence.codec import decode_value, encode_value
from coeus.services.prioritisation import (
    PRIORITISATION_AGENT,
    assessment_or_computed,
    prioritisation_agent_run,
    priority_sort_key,
    with_assessment,
)


def _ticket(intake: IntakeDetails, created_at: datetime | None = None) -> TicketRecord:
    return TicketRecord(
        ticket_id=uuid4(),
        reference="TCK-TEST",
        requester_user_id=uuid4(),
        state=TicketState.DRAFT_INTAKE,
        intake=intake,
        created_at=created_at or datetime.now(UTC),
    )


def test_urgent_special_forces_russia_request_is_p1_with_full_score() -> None:
    assessment = assess_intake(
        IntakeDetails(
            priority="critical",
            area_or_region="Russia, Kaliningrad approaches",
            requesting_unit="Task Group Kestrel",
            supported_operation="Operation Onyx Talon",
        )
    )

    assert assessment.score == 1.0
    assert assessment.tier == "P1"
    assert assessment.reasons == (
        "priority:level:critical",
        "priority:region:tier-1:russia",
        "priority:unit:special-forces",
        "priority:operation:special-forces:onyx-talon",
    )


def test_routine_request_with_no_ranking_signals_is_p4() -> None:
    assessment = assess_intake(IntakeDetails(priority="routine"))

    assert assessment.tier == "P4"
    assert assessment.reasons == (
        "priority:level:routine",
        "priority:region:standard",
        "priority:unit:unstated",
        "priority:operation:none",
    )


@pytest.mark.parametrize(
    ("region", "expected"),
    [
        ("Baltic ports", "priority:region:tier-1:baltic"),
        ("Middle East corridors", "priority:region:tier-2:middle-east"),
        ("Indo-Pacific approaches", "priority:region:tier-3:indo-pacific"),
        ("Atlantic seaboard", "priority:region:standard"),
        (None, "priority:region:standard"),
    ],
)
def test_region_tiers_match_by_substring(region: str | None, expected: str) -> None:
    assessment = assess_intake(IntakeDetails(area_or_region=region))

    assert expected in assessment.reasons


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        ("Task Group Kestrel", "priority:unit:special-forces"),
        ("Joint Intelligence Fusion Cell", "priority:unit:intelligence"),
        ("Carrier Strike Group Atlas", "priority:unit:carrier-group"),
        ("1st Field Army HQ", "priority:unit:field-army"),
        ("Air Station Greymoor", "priority:unit:air-base"),
        ("Harbour Authority Liaison", "priority:unit:uncategorised"),
        (None, "priority:unit:unstated"),
    ],
)
def test_unit_categories_follow_the_demanded_precedence(unit: str | None, expected: str) -> None:
    assessment = assess_intake(IntakeDetails(requesting_unit=unit))

    assert expected in assessment.reasons


@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        ("Operation Sable Wraith", "priority:operation:special-forces:sable-wraith"),
        ("Operation Iron Bulwark", "priority:operation:conventional:iron-bulwark"),
        ("Operation Harbour Sentinel", "priority:operation:standing-task:harbour-sentinel"),
        ("Exercise Baltic Resolve", "priority:operation:exercise:baltic-resolve"),
        ("Operation Unknown Falcon", "priority:operation:unregistered"),
        (None, "priority:operation:none"),
    ],
)
def test_operation_types_rank_special_forces_above_conventional(
    operation: str | None, expected: str
) -> None:
    assessment = assess_intake(IntakeDetails(supported_operation=operation))

    assert expected in assessment.reasons


@pytest.mark.parametrize(
    ("priority", "expected"),
    [
        ("critical", "priority:level:critical"),
        ("HIGH", "priority:level:high"),
        ("medium", "priority:level:medium"),
        ("routine", "priority:level:routine"),
        ("low", "priority:level:low"),
        ("bizarre", "priority:level:unstated"),
        (None, "priority:level:unstated"),
    ],
)
def test_priority_levels_are_case_insensitive(priority: str | None, expected: str) -> None:
    assert expected in assess_intake(IntakeDetails(priority=priority)).reasons


def test_assessment_is_deterministic_for_the_same_intake() -> None:
    intake = IntakeDetails(priority="high", area_or_region="Baltic")

    assert assess_intake(intake) == assess_intake(intake)


def test_queues_sort_by_score_then_oldest_first() -> None:
    early = datetime(2026, 7, 1, tzinfo=UTC)
    late = datetime(2026, 7, 9, tzinfo=UTC)
    routine_old = _ticket(IntakeDetails(priority="routine"), created_at=early)
    urgent_new = with_assessment(
        _ticket(
            IntakeDetails(
                priority="critical",
                area_or_region="Russia",
                requesting_unit="Task Group Kestrel",
                supported_operation="Operation Onyx Talon",
            ),
            created_at=late,
        )
    )
    routine_new = _ticket(IntakeDetails(priority="routine"), created_at=late)

    ordered = sorted((routine_new, routine_old, urgent_new), key=priority_sort_key)

    assert ordered == [urgent_new, routine_old, routine_new]


def test_legacy_tickets_without_a_stored_assessment_are_scored_on_the_fly() -> None:
    legacy = _ticket(IntakeDetails(priority="critical", area_or_region="Russia"))

    assert legacy.priority_assessment is None
    assert assessment_or_computed(legacy) == assess_intake(legacy.intake)


def test_agent_run_records_the_tier_score_and_reasons() -> None:
    ticket = with_assessment(_ticket(IntakeDetails(priority="critical", area_or_region="Russia")))
    assessment = assessment_or_computed(ticket)

    run = prioritisation_agent_run(ticket, assessment)

    assert run.agent_name == PRIORITISATION_AGENT
    assert f"Internal priority {assessment.tier}" in run.summary
    assert "priority:region:tier-1:russia" in run.summary


def test_priority_assessment_survives_a_codec_round_trip() -> None:
    ticket = with_assessment(_ticket(IntakeDetails(priority="high", area_or_region="Baltic")))

    decoded = decode_value(encode_value(ticket))

    assert isinstance(decoded, TicketRecord)
    assert isinstance(decoded.priority_assessment, PriorityAssessment)
    assert decoded.priority_assessment == ticket.priority_assessment
