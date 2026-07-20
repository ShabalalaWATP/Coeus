from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from coeus.domain.advisory_agents import AdvisoryAgentKind, AgentAdvice, AgentAdviceProvenance
from coeus.domain.enums import TicketState
from coeus.domain.jioc_routing import JiocRoutingContext, JiocRoutingDecision
from coeus.domain.outbox import OutboxMessage
from coeus.domain.tickets import (
    CmCapabilityReview,
    IntakeDetails,
    RfaCapabilityReview,
    TicketRecord,
)
from coeus.services.routing_critic_intent import ROUTING_CRITIQUE_REQUESTED
from coeus.services.routing_critic_outbox_handler import RoutingCriticOutboxHandler

NOW = datetime(2026, 7, 20, 12, tzinfo=UTC)


class _TicketStore:
    def __init__(self, ticket: TicketRecord) -> None:
        self.ticket = ticket

    def assignment_snapshot(self) -> tuple[TicketRecord, ...]:
        return (self.ticket,)


class _Mutations:
    def __init__(self, store: _TicketStore) -> None:
        self.store = store
        self.writes = 0

    def save_audited_if_current(
        self, _expected: TicketRecord, proposed: TicketRecord, *_args: object
    ) -> TicketRecord:
        self.writes += 1
        self.store.ticket = proposed
        return proposed


class _Critic:
    def __init__(self) -> None:
        self.observed: list[tuple[object, ...]] = []

    def critique_case(
        self,
        requester_id,
        context,
        decision,
        rfa,
        cm,
        committed_state,  # type: ignore[no-untyped-def]
    ) -> AgentAdvice:
        self.observed.append(
            (
                requester_id,
                context.context_id,
                decision.decision_id,
                rfa.review_id,
                cm.review_id,
                committed_state,
            )
        )
        return AgentAdvice(
            AdvisoryAgentKind.ROUTING_CRITIC,
            (),
            AgentAdviceProvenance(
                False,
                False,
                "local_provider",
                "mock",
                "mock",
                None,
                "not_applicable",
                "deterministic",
                "critic-v1",
                "policy-v1",
                "context-v1",
            ),
            verdict="supports",
            shadow_only=True,
            context_references=(f"decision:{decision.decision_id}",),
        )


def _case() -> tuple[TicketRecord, dict[str, str]]:
    ticket_id = uuid4()
    context = JiocRoutingContext(
        uuid4(),
        ticket_id,
        "jioc-routing-context-v1",
        "a" * 64,
        "no_match",
        "definitive",
        "complete",
        "corpus-v1",
        (),
        True,
        (),
        "routine",
        None,
        "brief",
        "analysis",
        "synthetic-region",
        "2026-07-01",
        "2026-07-20",
        False,
        NOW,
        "catalogue-v1",
        NOW,
        ("team-rfa:available:1",),
        300,
    )
    decision = JiocRoutingDecision(
        uuid4(),
        ticket_id,
        context.context_id,
        "rfa",
        "auto_applied",
        0.9,
        ("existing_information_assessment",),
        (),
        "jioc-routing-policy-v2",
        NOW,
        "eligible_rfa",
    )
    rfa = RfaCapabilityReview(
        uuid4(),
        ticket_id,
        True,
        0.9,
        (),
        ("assess",),
        "team-rfa",
        "medium",
        (),
        False,
        "Application-owned summary.",
        NOW,
    )
    cm = CmCapabilityReview(
        uuid4(),
        ticket_id,
        False,
        0.2,
        (),
        None,
        (),
        "unknown",
        (),
        False,
        "Application-owned summary.",
        NOW,
        None,
    )
    ticket = TicketRecord(
        ticket_id,
        "TCK-CRITIC-OUTBOX",
        uuid4(),
        TicketState.ANALYST_ASSIGNMENT,
        IntakeDetails(title="Synthetic case"),
        jioc_routing_contexts=(context,),
        jioc_routing_decisions=(decision,),
        rfa_reviews=(rfa,),
        cm_reviews=(cm,),
    )
    payload = {
        "decision_id": str(decision.decision_id),
        "context_id": str(context.context_id),
        "rfa_review_id": str(rfa.review_id),
        "cm_review_id": str(cm.review_id),
        "committed_state": TicketState.ANALYST_ASSIGNMENT.value,
    }
    return ticket, payload


def _message(ticket: TicketRecord, payload: dict[str, object]) -> OutboxMessage:
    return OutboxMessage(uuid4(), ticket.ticket_id, 1, ROUTING_CRITIQUE_REQUESTED, payload, NOW, 0)


def test_handler_uses_exact_evidence_and_is_retry_idempotent() -> None:
    ticket, payload = _case()
    store = _TicketStore(ticket)
    mutations = _Mutations(store)
    critic = _Critic()
    handler = RoutingCriticOutboxHandler(
        SimpleNamespace(tickets=store, mutations=mutations),  # type: ignore[arg-type]
        critic,  # type: ignore[arg-type]
    )

    handler(_message(ticket, payload))
    handler(_message(ticket, payload))

    assert len(critic.observed) == 1
    assert critic.observed[0][-1] is TicketState.ANALYST_ASSIGNMENT
    assert mutations.writes == 1
    assert store.ticket.agent_runs[-1].advice is not None
    assert store.ticket.agent_runs[-1].advice.shadow_only


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"decision_id": "not-a-uuid"},
        {
            "decision_id": str(uuid4()),
            "context_id": str(uuid4()),
            "rfa_review_id": str(uuid4()),
            "cm_review_id": str(uuid4()),
            "committed_state": "not-a-state",
        },
    ],
)
def test_handler_rejects_malformed_or_unlinked_payload(payload: dict[str, object]) -> None:
    ticket, _valid = _case()
    store = _TicketStore(ticket)
    handler = RoutingCriticOutboxHandler(
        SimpleNamespace(tickets=store, mutations=_Mutations(store)),  # type: ignore[arg-type]
        _Critic(),  # type: ignore[arg-type]
    )

    with pytest.raises((LookupError, ValueError)):
        handler(_message(ticket, payload))
