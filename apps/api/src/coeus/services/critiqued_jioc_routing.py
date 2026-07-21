"""Post-decision observer which cannot affect the committed JIOC route."""

from dataclasses import replace
from uuid import UUID

from coeus.application.ports.jioc_routing import JiocRoutingService
from coeus.core.logging import get_logger
from coeus.domain.advisory_agents import AdvisoryAgentKind
from coeus.domain.agent_names import JIOC_ROUTING_CRITIC_AGENT
from coeus.domain.tickets import TicketRecord
from coeus.services.advisory_records import advisory_agent_run
from coeus.services.jioc_routing_agent import JIOC_AGENT_PRINCIPAL
from coeus.services.routing_critic_agent import RoutingCriticAgent
from coeus.services.ticket_mutations import TicketMutationService

logger = get_logger(__name__)


class CritiquedJiocRoutingService:
    """Apply deterministic routing first, then best-effort shadow criticism."""

    def __init__(
        self,
        router: JiocRoutingService,
        critic: RoutingCriticAgent,
        mutations: TicketMutationService,
    ) -> None:
        self._router = router
        self._critic = critic
        self._mutations = mutations

    def route(self, ticket_id: UUID, *, apply: bool = True) -> TicketRecord:
        committed = self._router.route(ticket_id, apply=apply)
        if not _has_critic_inputs(committed) or _already_critiqued(committed):
            return committed
        try:
            advice = self._critic.critique(committed.requester_user_id, committed)
            run = advisory_agent_run(
                committed.ticket_id,
                JIOC_ROUTING_CRITIC_AGENT,
                "Shadow critic reviewed the committed deterministic route.",
                advice,
            )
            proposed = replace(committed, agent_runs=(*committed.agent_runs, run))
            return self._mutations.save_audited_if_current(
                committed,
                proposed,
                "jioc_routing_critique_recorded",
                JIOC_AGENT_PRINCIPAL,
                {
                    "ticket_id": str(committed.ticket_id),
                    "decision_id": str(committed.jioc_routing_decisions[-1].decision_id),
                    "critic_version": advice.provenance.policy_version,
                    "verdict": advice.verdict or "unavailable",
                },
            )
        except Exception as error:
            logger.exception(
                "jioc_routing_critique_failed",
                extra={"ticket_id": str(ticket_id), "error": type(error).__name__},
            )
            return committed

    def defer_to_manager(
        self, ticket_id: UUID, reason: str = "routing_automation_disabled"
    ) -> TicketRecord:
        return self._router.defer_to_manager(ticket_id, reason)


def _has_critic_inputs(ticket: TicketRecord) -> bool:
    return bool(
        ticket.jioc_routing_contexts
        and ticket.jioc_routing_decisions
        and ticket.rfa_reviews
        and ticket.cm_reviews
    )


def _already_critiqued(ticket: TicketRecord) -> bool:
    decision_ref = f"decision:{ticket.jioc_routing_decisions[-1].decision_id}"
    return any(
        run.advice is not None
        and run.advice.agent is AdvisoryAgentKind.ROUTING_CRITIC
        and decision_ref in run.advice.context_references
        for run in ticket.agent_runs
    )
