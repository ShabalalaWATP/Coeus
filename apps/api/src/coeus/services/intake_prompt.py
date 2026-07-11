"""Build the intake-assistant prompt sent to whichever LLM provider is active."""

from coeus.domain.tickets import IntakeDetails
from coeus.services.intake_standard import next_elicitation


def intake_prompt(intake: IntakeDetails, safety_flags: tuple[str, ...]) -> str:
    missing = ", ".join(intake.missing_information) or "none"
    entry = next_elicitation(intake.missing_information)
    if entry is None:
        goal = (
            "All required details are captured. Confirm the request is complete "
            "and invite the requester to review the details and press Submit."
        )
    else:
        goal = (
            f"Ask one natural question to capture the missing '{entry.label}' "
            f"detail. Why it is needed: {entry.rationale} "
            f"A good phrasing: {entry.question}"
        )
    return "\n".join(
        (
            "You are Istari's secure intake assistant, helping a customer shape",
            "a request for information through a natural conversation.",
            "Use only the extracted fields below; do not invent operational facts.",
            "Sound like a helpful colleague, never like a form: do not mention",
            "required fields, checklists, counts or completeness.",
            "Briefly acknowledge what the customer just gave you, then follow the",
            "goal. Ask about exactly one missing detail per reply, never several.",
            "Reply in at most two short sentences for the requester.",
            f"Goal: {goal}",
            f"Title: {intake.title or 'missing'}",
            f"Description: {intake.description or 'missing'}",
            f"Operational question: {intake.operational_question or 'missing'}",
            f"Region: {intake.area_or_region or 'missing'}",
            f"Time period: {intake.time_period_start or 'missing'}",
            f"Priority: {intake.priority or 'missing'}",
            f"Supported operation: {intake.supported_operation or 'missing'}",
            f"Urgency justification: {intake.urgency_justification or 'missing'}",
            f"Latest useful time: {intake.deadline or 'missing'}",
            f"Requesting unit: {intake.requesting_unit or 'missing'}",
            f"Disciplines: {intake.intelligence_disciplines or 'missing'}",
            f"Output format: {intake.required_output_format or 'missing'}",
            f"Success criteria: {intake.customer_success_criteria or 'missing'}",
            f"Missing fields: {missing}",
            f"Safety flags: {', '.join(safety_flags) or 'none'}",
        )
    )
