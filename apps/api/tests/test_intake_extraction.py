from coeus.services.intake import IntakeExtractionService


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
    assert intake.missing_information == ()


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
