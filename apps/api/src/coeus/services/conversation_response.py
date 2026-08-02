"""Deterministic intake conversation lifecycle and response selection."""

from collections.abc import Callable

from coeus.domain.tickets import IntakeDetails
from coeus.services import conversation_lifecycle as lifecycle
from coeus.services.conversation_reply_records import deterministic_reply
from coeus.services.intake import AdmittedAssistantReply
from coeus.services.intake_planner import deterministic_intake_plan
from coeus.services.intake_planner_advice import render_intake_plan
from coeus.services.intake_standard import next_elicitation


def conversation_reply_and_status(
    status: str,
    message: str,
    intake: IntakeDetails,
    planned_reply: Callable[[IntakeDetails], AdmittedAssistantReply],
) -> tuple[AdmittedAssistantReply, str]:
    plan = deterministic_intake_plan(intake, intake.missing_information)
    blocked = bool(plan.contradictions)
    complete = not intake.missing_information and not blocked
    offered = status == lifecycle.CONVERSATION_CLOSE_OFFERED
    if offered and complete and lifecycle.confirms_close(message):
        return deterministic_reply(lifecycle.CLOSED_MESSAGE, "conversation_closed"), (
            lifecycle.CONVERSATION_CLOSED
        )
    if lifecycle.wants_to_end(message):
        if complete:
            return deterministic_reply(
                lifecycle.CLOSED_MESSAGE, "conversation_closed"
            ), lifecycle.CONVERSATION_CLOSED
        entry = next_elicitation(intake.missing_information)
        question = (
            render_intake_plan(plan, intake) if blocked else (entry.question if entry else "")
        )
        return (
            deterministic_reply(
                lifecycle.cannot_close_message(question).strip(),
                (
                    "close_refused_intake_contradiction"
                    if blocked
                    else "close_refused_missing_information"
                ),
            ),
            lifecycle.CONVERSATION_OPEN,
        )
    if blocked or plan.ambiguities:
        return planned_reply(intake), lifecycle.CONVERSATION_OPEN
    if complete:
        return deterministic_reply(
            lifecycle.CLOSE_OFFER_MESSAGE, "close_offered"
        ), lifecycle.CONVERSATION_CLOSE_OFFERED
    return planned_reply(intake), lifecycle.CONVERSATION_OPEN
