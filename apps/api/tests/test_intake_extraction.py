from coeus.domain.tickets import IntakeDetails
from coeus.services.intake import IntakeExtractionService, MockLlmProvider


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
    assert intake.missing_information == ("operational_question",)


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


def test_mock_provider_confirms_a_complete_intake() -> None:
    reply = MockLlmProvider().build_assistant_message(IntakeDetails(missing_information=()), ())

    assert reply == "The intake is complete enough to submit for controlled search."
