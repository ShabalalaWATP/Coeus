from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.jioc_intervention import JiocIntervention
from coeus.domain.tickets import TicketRecord
from coeus.services.ticket_records import timeline
from coeus.services.tickets import TicketServices

HOLDABLE_STATES = frozenset(
    {
        TicketState.JIOC_ROUTING_PENDING,
        TicketState.JIOC_REVIEW,
        TicketState.COLLECT_CHOICE,
        TicketState.ANALYST_ASSIGNMENT,
        TicketState.ANALYST_IN_PROGRESS,
        TicketState.MANAGER_APPROVAL,
        TicketState.QC_REVIEW,
        TicketState.REWORK_REQUIRED,
    }
)
REVIEWABLE_STATES = frozenset(
    {
        TicketState.JIOC_ROUTING_PENDING,
        TicketState.COLLECT_CHOICE,
        TicketState.ANALYST_ASSIGNMENT,
    }
)


class JiocInterventionService:
    def __init__(self, tickets: TicketServices) -> None:
        self._tickets = tickets

    def hold(self, actor: UserAccount, ticket_id: UUID, reason: str) -> TicketRecord:
        self._require(actor)
        ticket = self._ticket(ticket_id)
        if ticket.state not in HOLDABLE_STATES:
            raise AppError(409, "invalid_ticket_state", "This request cannot be placed on hold.")
        now = datetime.now(UTC)
        intervention = JiocIntervention(
            uuid4(),
            ticket.ticket_id,
            "hold",
            reason,
            ticket.state.value,
            actor.user_id,
            now,
        )
        return self._save(ticket, actor, TicketState.JIOC_INTERVENTION_HOLD, intervention)

    def resume(self, actor: UserAccount, ticket_id: UUID, reason: str) -> TicketRecord:
        self._require(actor)
        ticket = self._ticket(ticket_id)
        active = next(
            (
                item
                for item in reversed(ticket.jioc_interventions)
                if item.action == "hold" and item.resumed_at is None
            ),
            None,
        )
        if ticket.state != TicketState.JIOC_INTERVENTION_HOLD or active is None:
            raise AppError(409, "invalid_ticket_state", "This request is not on JIOC hold.")
        target = TicketState(active.previous_state)
        resumed_at = datetime.now(UTC)
        completed_hold = replace(
            active,
            resumed_at=resumed_at,
            resumed_by_user_id=actor.user_id,
        )
        resume = JiocIntervention(
            uuid4(),
            ticket.ticket_id,
            "resume",
            reason,
            target.value,
            actor.user_id,
            resumed_at,
        )
        history = tuple(
            completed_hold if item.intervention_id == active.intervention_id else item
            for item in ticket.jioc_interventions
        )
        return self._save(ticket, actor, target, resume, (*history, resume))

    def send_to_review(self, actor: UserAccount, ticket_id: UUID, reason: str) -> TicketRecord:
        self._require(actor)
        ticket = self._ticket(ticket_id)
        if ticket.state not in REVIEWABLE_STATES:
            raise AppError(409, "invalid_ticket_state", "This request cannot be rerouted now.")
        intervention = JiocIntervention(
            uuid4(),
            ticket.ticket_id,
            "send_to_review",
            reason,
            ticket.state.value,
            actor.user_id,
            datetime.now(UTC),
        )
        return self._save(ticket, actor, TicketState.JIOC_REVIEW, intervention)

    def _save(
        self,
        ticket: TicketRecord,
        actor: UserAccount,
        target: TicketState,
        intervention: JiocIntervention,
        interventions: tuple[JiocIntervention, ...] | None = None,
    ) -> TicketRecord:
        records = interventions or (*ticket.jioc_interventions, intervention)
        return self._tickets.mutations.save_audited_if_current(
            ticket,
            replace(
                ticket,
                state=target,
                jioc_interventions=records,
                timeline=(
                    *ticket.timeline,
                    timeline(
                        ticket.ticket_id,
                        actor.user_id,
                        f"jioc_intervention_{intervention.action}",
                        "A JIOC manager intervened in this request.",
                    ),
                ),
            ),
            f"jioc_intervention_{intervention.action}",
            actor,
            {"ticket_id": str(ticket.ticket_id), "reason": intervention.reason},
        )

    def _ticket(self, ticket_id: UUID) -> TicketRecord:
        ticket = next(
            (
                item
                for item in self._tickets.tickets.assignment_snapshot()
                if item.ticket_id == ticket_id
            ),
            None,
        )
        if ticket is None:
            raise AppError(404, "ticket_not_found", "Ticket was not found.")
        return ticket

    @staticmethod
    def _require(actor: UserAccount) -> None:
        if Permission.JIOC_INTERVENE not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
