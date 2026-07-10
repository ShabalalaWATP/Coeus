"""Ticket-facing helpers for the deterministic priority ranking.

The assessment is stored on the ticket whenever the intake changes so queues
sort without recomputation, and a ``prioritisation-agent`` run records the
submit-time snapshot for the audit trail. Legacy tickets persisted before the
ranking existed are scored on the fly; the function is deterministic, so the
stored and computed values can never disagree for the same intake.
"""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from coeus.domain.prioritisation import PriorityAssessment, assess_intake
from coeus.domain.tickets import AgentRun, AgentRunStatus, TicketRecord

PRIORITISATION_AGENT = "prioritisation-agent"


def with_assessment(ticket: TicketRecord) -> TicketRecord:
    return replace(ticket, priority_assessment=assess_intake(ticket.intake))


def assessment_or_computed(ticket: TicketRecord) -> PriorityAssessment:
    return ticket.priority_assessment or assess_intake(ticket.intake)


def priority_sort_key(ticket: TicketRecord) -> tuple[float, datetime]:
    """Queue ordering: highest score first, then oldest first."""
    return (-assessment_or_computed(ticket).score, ticket.created_at)


def prioritisation_agent_run(ticket: TicketRecord, assessment: PriorityAssessment) -> AgentRun:
    return AgentRun(
        run_id=uuid4(),
        ticket_id=ticket.ticket_id,
        agent_name=PRIORITISATION_AGENT,
        status=AgentRunStatus.COMPLETED,
        summary=(
            f"Internal priority {assessment.tier} (score {assessment.score}): "
            + ", ".join(assessment.reasons)
        ),
        safety_flags=(),
        created_at=datetime.now(UTC),
    )
