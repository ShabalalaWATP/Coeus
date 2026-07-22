"""Retry-safe worker for durable post-commit routing criticism."""

from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

from coeus.domain.advisory_agents import AdvisoryAgentKind
from coeus.domain.enums import TicketState
from coeus.domain.outbox import OutboxMessage
from coeus.domain.tickets import TicketRecord
from coeus.services.advisory_records import advisory_agent_run
from coeus.services.jioc_routing_agent import JIOC_AGENT_PRINCIPAL
from coeus.services.routing_critic_agent import RoutingCriticAgent
from coeus.services.routing_critic_intent import ROUTING_CRITIQUE_REQUESTED
from coeus.services.tickets import TicketServices

_PAYLOAD_KEYS = frozenset(
    {"decision_id", "context_id", "rfa_review_id", "cm_review_id", "committed_state"}
)


@dataclass(frozen=True)
class RoutingCritiquePayload:
    decision_id: UUID
    context_id: UUID
    rfa_review_id: UUID
    cm_review_id: UUID
    committed_state: TicketState


class RoutingCriticOutboxHandler:
    def __init__(self, tickets: TicketServices, critic: RoutingCriticAgent) -> None:
        self._tickets = tickets
        self._critic = critic

    def __call__(self, message: OutboxMessage) -> None:
        if message.event_type != ROUTING_CRITIQUE_REQUESTED:
            raise ValueError("Unexpected outbox event type for routing criticism.")
        payload = _payload(message.payload)
        ticket = _ticket(self._tickets, message.aggregate_id)
        decision_ref = f"decision:{payload.decision_id}"
        if _already_recorded(ticket, decision_ref):
            return
        context = _by_id(ticket.jioc_routing_contexts, "context_id", payload.context_id)
        decision = _by_id(ticket.jioc_routing_decisions, "decision_id", payload.decision_id)
        rfa = _by_id(ticket.rfa_reviews, "review_id", payload.rfa_review_id)
        cm = _by_id(ticket.cm_reviews, "review_id", payload.cm_review_id)
        if not (
            decision.context_id == context.context_id == payload.context_id
            and decision.ticket_id == context.ticket_id == rfa.ticket_id == cm.ticket_id
            and decision.ticket_id == ticket.ticket_id
        ):
            raise ValueError("Routing critique evidence linkage is invalid.")
        advice = self._critic.critique_case(
            ticket.requester_user_id,
            context,
            decision,
            rfa,
            cm,
            payload.committed_state,
        )
        if decision_ref not in advice.context_references:
            raise ValueError("Routing critique did not reference the requested decision.")
        run = advisory_agent_run(
            ticket.ticket_id,
            "jioc-routing-critic-agent",
            "Shadow critic reviewed the committed deterministic route.",
            advice,
        )
        self._tickets.mutations.save_audited_if_current(
            ticket,
            replace(ticket, agent_runs=(*ticket.agent_runs, run)),
            "jioc_routing_critique_recorded",
            JIOC_AGENT_PRINCIPAL,
            {
                "ticket_id": str(ticket.ticket_id),
                "decision_id": str(payload.decision_id),
                "critic_version": advice.provenance.policy_version,
                "verdict": advice.verdict or "unavailable",
            },
        )


def _payload(value: dict[str, Any]) -> RoutingCritiquePayload:
    if set(value) != _PAYLOAD_KEYS or any(not isinstance(item, str) for item in value.values()):
        raise ValueError("Invalid routing critique payload.")
    try:
        return RoutingCritiquePayload(
            UUID(value["decision_id"]),
            UUID(value["context_id"]),
            UUID(value["rfa_review_id"]),
            UUID(value["cm_review_id"]),
            TicketState(value["committed_state"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Invalid routing critique payload.") from error


def _ticket(tickets: TicketServices, ticket_id: UUID) -> TicketRecord:
    ticket = next(
        (item for item in tickets.tickets.assignment_snapshot() if item.ticket_id == ticket_id),
        None,
    )
    if ticket is None:
        raise LookupError("Routing critique ticket was not found.")
    return ticket


def _by_id(values: tuple[Any, ...], field: str, expected: UUID) -> Any:
    value = next((item for item in values if getattr(item, field) == expected), None)
    if value is None:
        raise LookupError("Routing critique evidence was not found.")
    return value


def _already_recorded(ticket: TicketRecord, decision_ref: str) -> bool:
    return any(
        run.advice is not None
        and run.advice.agent is AdvisoryAgentKind.ROUTING_CRITIC
        and decision_ref in run.advice.context_references
        for run in ticket.agent_runs
    )
