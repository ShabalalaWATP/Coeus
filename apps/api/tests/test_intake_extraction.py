from dataclasses import replace

from coeus.domain.tickets import IntakeDetails
from coeus.services.intake import (
    IntakeExtractionService,
    MockLlmProvider,
    RequirementCompletenessService,
)


def test_intake_extraction_handles_natural_demo_phrasing() -> None:
    intake = IntakeExtractionService().extract(
        "Need a priority assessment of vessel activity near the North Atlantic shipping lanes "
        "by Friday. Priority is routine. Include likely origin ports and confidence levels."
    )

    assert intake.area_or_region == "North Atlantic Shipping Lanes"
    assert intake.deadline == "Friday"
    assert intake.priority == "routine"
    assert intake.required_output_format == "Assessment"
    assert intake.customer_success_criteria == "Include likely origin ports and confidence levels."
    # No question was asked, so none is invented for the customer.
    assert intake.operational_question is None
    assert intake.missing_information == (
        "operational_question",
        "time_period",
        "requesting_unit",
        "intelligence_disciplines",
    )


def test_intake_extraction_handles_time_windows_and_decision_phrasing() -> None:
    intake = IntakeExtractionService().extract(
        "Need a map and briefing for Baltic ports next week, high priority, "
        "so that commanders can decide patrol posture."
    )

    assert intake.area_or_region == "Baltic Ports"
    assert intake.priority == "high"
    assert intake.required_output_format == "Briefing note"
    assert intake.time_period_start == "next week"
    assert intake.time_period_end == "next week"
    assert intake.customer_success_criteria == "So that commanders can decide patrol posture."


def test_intake_extraction_never_invents_question_or_success_criteria() -> None:
    intake = IntakeExtractionService().extract(
        "Need an assessment of coastal radar coverage to support a command decision."
    )

    assert intake.operational_question is None
    assert intake.customer_success_criteria is None
    assert "operational_question" in intake.missing_information
    assert "customer_success_criteria" in intake.missing_information


def test_intake_extraction_lifts_only_a_question_the_customer_asked() -> None:
    intake = IntakeExtractionService().extract(
        "Need a brief. Which ports are seeing unusual vessel activity?"
    )

    assert intake.operational_question == (
        "Need a brief. Which ports are seeing unusual vessel activity?"
    )


def test_intake_title_falls_back_only_for_requirement_statements() -> None:
    service = IntakeExtractionService()

    casual = service.extract("Hello there, how is everyone today.")
    requirement = service.extract("Need a summary of mock harbour movements.")
    titled = service.extract("Give me something titled Harbour Watch for the Baltic.")

    assert casual.title is None
    assert requirement.title == "Need A Summary Of Mock Harbour"
    assert titled.title == "Harbour Watch"


def test_intake_extraction_recognises_each_output_format() -> None:
    service = IntakeExtractionService()

    assert service.extract("Need slides on mock port readiness.").required_output_format == (
        "Slide deck"
    )
    assert service.extract("Need a spreadsheet of vessel arrivals.").required_output_format == (
        "Data table"
    )
    assert service.extract("Need a report on mock rail disruption.").required_output_format == (
        "Report"
    )
    assert service.extract("Need a geojson layer of crossings.").required_output_format == (
        "Geospatial layer"
    )


def test_intake_extraction_handles_date_ranges_regions_and_deadline_clauses() -> None:
    intake = IntakeExtractionService().extract(
        "Need a report on movements in a northern corridor from 2025-01-01 to 2025-02-01, "
        "due by Friday with maps. Success criteria: highlight new crossings."
    )

    assert intake.time_period_start == "2025-01-01"
    assert intake.time_period_end == "2025-02-01"
    assert intake.area_or_region == "Northern Corridor"
    assert intake.deadline == "Friday"
    assert intake.customer_success_criteria == "Success criteria: highlight new crossings."


def test_intake_extraction_captures_operation_unit_and_disciplines() -> None:
    intake = IntakeExtractionService().extract(
        "Need an urgent report in support of Operation Onyx Talon for Carrier "
        "Strike Group Atlas; satellite imagery and open source reporting would help."
    )

    assert intake.priority == "high"
    assert intake.supported_operation == "Operation Onyx Talon"
    assert intake.requesting_unit == "Carrier Strike Group Atlas"
    assert intake.intelligence_disciplines == "IMINT, OSINT"
    assert intake.urgency_justification is not None


def test_intake_extraction_recognises_exercises_and_preceding_unit_names() -> None:
    intake = IntakeExtractionService().extract(
        "Need a brief. This supports EX BALTIC RESOLVE for the 4th Armoured Brigade."
    )

    assert intake.supported_operation == "Exercise Baltic Resolve"
    assert intake.requesting_unit == "4th Armoured Brigade"


def test_new_extractors_stay_silent_without_explicit_cues() -> None:
    intake = IntakeExtractionService().extract(
        "Need a report on unusual vessel movements around mock harbours."
    )

    assert intake.supported_operation is None
    assert intake.requesting_unit is None
    assert intake.intelligence_disciplines is None
    assert intake.urgency_justification is None


def test_urgent_priority_expands_the_required_information() -> None:
    service = RequirementCompletenessService()
    base = IntakeDetails(
        title="Harbour Watch",
        description="Assess mock harbour movements.",
        operational_question="What changed?",
        area_or_region="Baltic",
        time_period_start="next week",
        requesting_unit="Carrier Strike Group Atlas",
        intelligence_disciplines="IMINT",
        required_output_format="Report",
        customer_success_criteria="Highlight changes.",
    )

    routine = service.with_completeness(replace(base, priority="routine"))
    urgent = service.with_completeness(replace(base, priority="critical"))

    assert routine.missing_information == ()
    assert routine.confidence == 1.0
    assert urgent.missing_information == (
        "supported_operation",
        "urgency_justification",
        "deadline",
    )
    assert urgent.confidence == round(10 / 13, 2)


def test_downgrading_priority_removes_the_urgent_requirements() -> None:
    service = RequirementCompletenessService()
    urgent = service.with_completeness(IntakeDetails(priority="high"))
    downgraded = service.with_completeness(IntakeDetails(priority="routine"))

    assert "urgency_justification" in urgent.missing_information
    assert "urgency_justification" not in downgraded.missing_information


def test_mock_provider_offers_to_finish_when_nothing_is_missing() -> None:
    reply = MockLlmProvider().build_assistant_message(IntakeDetails(missing_information=()), ())

    assert reply == (
        "I think I have everything I need. Is there anything else you "
        "would like to add, or shall we finish here?"
    )


def test_mock_provider_asks_one_question_at_a_time_in_standard_order() -> None:
    provider = MockLlmProvider()

    first = provider.build_assistant_message(
        IntakeDetails(missing_information=("operational_question", "priority", "title")),
        (),
    )
    second = provider.build_assistant_message(
        IntakeDetails(missing_information=("title", "priority")),
        (),
    )

    assert first == (
        "Got it. What is the specific question you would like answered? "
        "Putting it as a question helps the analysts focus the work."
    )
    assert second == "Got it. How urgent is this for you: critical, high, medium, routine or low?"


def test_mock_provider_varies_acknowledgements_as_details_accumulate() -> None:
    provider = MockLlmProvider()
    sparse = IntakeDetails(missing_information=("priority",))
    fuller = IntakeDetails(
        title="Harbour Watch",
        description="Assess mock harbour movements.",
        missing_information=("priority",),
    )

    sparse_reply = provider.build_assistant_message(sparse, ())
    fuller_reply = provider.build_assistant_message(fuller, ())

    assert sparse_reply != fuller_reply
    assert sparse_reply.endswith("critical, high, medium, routine or low?")
    assert fuller_reply.endswith("critical, high, medium, routine or low?")
