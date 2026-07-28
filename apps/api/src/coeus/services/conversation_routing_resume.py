"""Resume routing review when a chat reply answers a clarification."""

from collections.abc import Callable
from uuid import UUID

from coeus.domain.enums import TicketState
from coeus.domain.routing_phase import routing_history_present
from coeus.domain.tickets import IntakeDetails, TicketRecord, TicketTimelineEntry
from coeus.services.ticket_records import timeline


def chat_reply_projection(
    ticket: TicketRecord,
    actor_user_id: UUID,
    intake: IntakeDetails,
    safety_flags: tuple[str, ...],
    state_for_intake: Callable[[TicketState, IntakeDetails], TicketState],
) -> tuple[TicketState, tuple[TicketTimelineEntry, ...]]:
    """Project the post-reply state and timeline for a requester chat message.

    A clarification answer on a routed ticket resumes JIOC review; it must
    never regress the ticket into the intake loop. Flagged messages are not
    treated as clarification answers.
    """
    resumed_routing = (
        ticket.state == TicketState.INFO_REQUIRED
        and routing_history_present(ticket)
        and not safety_flags
    )
    state = TicketState.JIOC_REVIEW if resumed_routing else state_for_intake(ticket.state, intake)
    entries = (
        *ticket.timeline,
        timeline(ticket.ticket_id, actor_user_id, "chat_message", "User chat received."),
    )
    if resumed_routing:
        entries = (
            *entries,
            timeline(
                ticket.ticket_id,
                actor_user_id,
                "route_assessment_resumed",
                "Requester clarification received.",
            ),
        )
    return state, entries
