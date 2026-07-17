from coeus.domain.tickets import IntakeDetails
from coeus.services import intake_extractors as extractors
from coeus.services.intake import IntakeExtractionService
from coeus.services.intake_answers import apply_direct_answer
from coeus.services.intake_transcripts import voice_turns


def test_direct_answer_rejects_non_answer_and_accepts_bounded_open_text() -> None:
    intake = IntakeDetails()

    unchanged = apply_direct_answer(intake, "area_or_region", "not sure")
    described = apply_direct_answer(
        intake,
        "description",
        "A sufficiently detailed synthetic harbour requirement.",
    )
    operation = apply_direct_answer(intake, "supported_operation", "Tasking Lantern")

    assert unchanged is intake
    assert described.known_context == described.description
    assert operation.supported_operation == "Tasking Lantern"


def test_direct_time_answer_accepts_rough_duration_but_preserves_existing_value() -> None:
    rough = apply_direct_answer(IntakeDetails(), "time_period", "three weeks")
    preserved = apply_direct_answer(rough, "time_period", "four weeks")

    assert rough.time_period_start == "three weeks"
    assert rough.time_period_end == "three weeks"
    assert preserved == rough


def test_voice_parser_handles_blank_continuation_and_user_first_turns() -> None:
    transcript = """Voice drafting transcript:

You: Assess synthetic harbour
activity before the exercise.
Istari: Which region?"""

    turns = voice_turns(transcript)
    intake = IntakeExtractionService().extract(transcript)

    assert turns is not None
    assert turns[0].text == "Assess synthetic harbour activity before the exercise."
    assert intake.description == "Assess synthetic harbour activity before the exercise."


def test_extractors_cover_rough_month_unit_urgency_and_four_digit_uk_dates() -> None:
    start, end = extractors.extract_time_window("the entirety of July")
    dated = extractors.extract_time_window("01/07/2025 to 1/07/2026")

    assert start == end == "the entirety of July"
    assert dated == ("2025-07-01", "2026-07-01")
    assert extractors.extract_requesting_unit("On behalf of Mock Analysis Cell") == (
        "Mock Analysis Cell"
    )
    assert (
        extractors.extract_urgency_justification(
            "This is critical because the synthetic exercise starts tomorrow."
        )
        == "This is critical because the synthetic exercise starts tomorrow."
    )
