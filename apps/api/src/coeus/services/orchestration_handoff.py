from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.domain.tickets import (
    AgentRun,
    AgentRunStatus,
    ChatMessage,
    ClarificationRequest,
    MessageAuthor,
    RoutingRoute,
    TicketRecord,
    TicketTimelineEntry,
)


@dataclass(frozen=True)
class ClarificationHandoff:
    clarification: ClarificationRequest
    message: ChatMessage
    agent_runs: tuple[AgentRun, ...]
    timeline: TicketTimelineEntry


def agent_clarification_handoff(
    ticket_id: UUID,
    actor_user_id: UUID,
    reason: str,
    questions: tuple[str, ...],
) -> ClarificationHandoff:
    return _handoff(
        ticket_id,
        actor_user_id,
        RoutingRoute.CLARIFICATION,
        reason,
        questions,
        "Routed capability-agent clarification questions to the requester.",
    )


def manager_clarification_handoff(
    ticket_id: UUID,
    actor_user_id: UUID,
    route: RoutingRoute,
    reason: str,
    questions: tuple[str, ...],
) -> ClarificationHandoff:
    return _handoff(
        ticket_id,
        actor_user_id,
        route,
        reason,
        questions,
        "Routed manager clarification questions to the requester.",
    )


def append_handoff(ticket: TicketRecord, handoff: ClarificationHandoff | None) -> TicketRecord:
    if handoff is None:
        return ticket
    return replace(
        ticket,
        clarification_requests=(*ticket.clarification_requests, handoff.clarification),
        messages=(*ticket.messages, handoff.message),
        agent_runs=(*ticket.agent_runs, *handoff.agent_runs),
        timeline=(*ticket.timeline, handoff.timeline),
    )


def _handoff(
    ticket_id: UUID,
    actor_user_id: UUID,
    route: RoutingRoute,
    reason: str,
    questions: tuple[str, ...],
    orchestrator_summary: str,
) -> ClarificationHandoff:
    cleaned_questions = _clean_questions(questions)
    return ClarificationHandoff(
        clarification=ClarificationRequest(
            clarification_id=uuid4(),
            ticket_id=ticket_id,
            route=route,
            reason=reason,
            questions=cleaned_questions,
            requested_by_user_id=actor_user_id,
            created_at=datetime.now(UTC),
        ),
        message=ChatMessage(
            message_id=uuid4(),
            ticket_id=ticket_id,
            author=MessageAuthor.ASSISTANT,
            body=_message_body(reason, cleaned_questions),
            created_at=datetime.now(UTC),
        ),
        agent_runs=(
            _agent_run(ticket_id, "orchestrator-agent", orchestrator_summary),
            _agent_run(
                ticket_id,
                "customer-chatbot-agent",
                "Asked the requester for clarification.",
            ),
        ),
        timeline=TicketTimelineEntry(
            entry_id=uuid4(),
            ticket_id=ticket_id,
            event_type="customer_clarification_sent",
            body="Clarification questions sent through the customer chatbot.",
            actor_user_id=actor_user_id,
            created_at=datetime.now(UTC),
        ),
    )


def _agent_run(ticket_id: UUID, agent_name: str, summary: str) -> AgentRun:
    return AgentRun(
        run_id=uuid4(),
        ticket_id=ticket_id,
        agent_name=agent_name,
        status=AgentRunStatus.COMPLETED,
        summary=summary,
        safety_flags=(),
        created_at=datetime.now(UTC),
    )


def _clean_questions(questions: tuple[str, ...]) -> tuple[str, ...]:
    cleaned = tuple(question.strip() for question in questions if question.strip())
    return cleaned or ("Please provide the missing detail needed to route this request.",)


def _message_body(reason: str, questions: tuple[str, ...]) -> str:
    question_lines = "\n".join(f"- {question}" for question in questions)
    return (
        "I need a bit more information before this request can continue.\n\n"
        f"Reason: {reason.strip()}\n\n"
        f"{question_lines}"
    )
