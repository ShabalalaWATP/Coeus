"""Deterministic intake submission gate."""

from coeus.core.errors import AppError
from coeus.domain.tickets import IntakeDetails
from coeus.services.intake import RequirementCompletenessService
from coeus.services.intake_planner import blocking_intake_reasons


def require_submittable_intake(intake: IntakeDetails) -> None:
    complete = RequirementCompletenessService().with_completeness(intake)
    if blocking_intake_reasons(complete):
        raise AppError(
            409,
            "intake_contradiction",
            "Resolve the contradictory intake dates before submission.",
        )
    if complete.missing_information:
        raise AppError(409, "intake_incomplete", "Complete the required intake fields first.")
