"""Customer satisfaction and human-controlled re-analysis workflow."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.customer_outcomes import (
    CustomerProductDecision,
    CustomerProductDecisionStatus,
    JiocReanalysisDecision,
    JiocReanalysisStatus,
    ManagerReanalysisDecision,
    ManagerReanalysisStatus,
)
from coeus.domain.enums import TicketState
from coeus.domain.state_machine import can_transition
from coeus.domain.tickets import RoutingRoute, TicketRecord, WorkPackageStatus
from coeus.services.analyst_records import active_assignments, approved_route, assigned_analyst_ids
from coeus.services.ticket_records import is_owner, timeline
from coeus.services.tickets import TicketServices

ROUTE_PERMISSIONS = {
    RoutingRoute.RFA: Permission.RFA_REVIEW,
    RoutingRoute.CM: Permission.COLLECTION_REVIEW,
}


class CustomerOutcomeService:
    def __init__(self, tickets: TicketServices) -> None:
        self._tickets = tickets

    def customer_decision(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        *,
        meets_requirement: bool,
        reason: str,
        unmet_criteria: tuple[str, ...],
    ) -> TicketRecord:
        ticket = self._tickets.tickets.get_visible_ticket(actor, ticket_id)
        if not is_owner(actor, ticket):
            raise AppError(403, "forbidden", "Only the requester can decide this outcome.")
        if ticket.state != TicketState.DISSEMINATION_READY or not ticket.disseminations:
            raise AppError(409, "invalid_ticket_state", "No released product is awaiting review.")
        status = (
            CustomerProductDecisionStatus.ACCEPTED
            if meets_requirement
            else CustomerProductDecisionStatus.REJECTED
        )
        if status is CustomerProductDecisionStatus.REJECTED and len(reason.strip()) < 3:
            raise AppError(422, "reason_required", "Explain why the product did not meet the need.")
        target = (
            TicketState.CLOSED_REQUIREMENT_MET
            if meets_requirement
            else TicketState.MANAGER_REANALYSIS_REVIEW
        )
        _require_transition(ticket, target)
        decision = CustomerProductDecision(
            uuid4(),
            ticket.ticket_id,
            ticket.disseminations[-1].product_id,
            status,
            reason.strip(),
            tuple(item.strip() for item in unmet_criteria if item.strip()),
            actor.user_id,
            datetime.now(UTC),
        )
        outcomes = replace(
            ticket.product_outcomes,
            customer_decisions=(*ticket.product_outcomes.customer_decisions, decision),
        )
        body = (
            "The requester confirmed that the released product met the requirement."
            if meets_requirement
            else "The requester explained that the released product did not meet the requirement."
        )
        return self._save(
            ticket,
            replace(
                ticket,
                state=target,
                product_outcomes=outcomes,
                timeline=(*ticket.timeline, timeline(ticket_id, actor.user_id, status.value, body)),
            ),
            "customer_product_accepted" if meets_requirement else "customer_product_rejected",
            actor,
        )

    def manager_decision(
        self, actor: UserAccount, ticket_id: UUID, *, agree: bool, rationale: str
    ) -> TicketRecord:
        if len(rationale.strip()) < 3:
            raise AppError(422, "reason_required", "A manager rationale is required.")
        ticket = self._workflow_ticket(actor, ticket_id)
        if ticket.state != TicketState.MANAGER_REANALYSIS_REVIEW:
            raise AppError(
                409, "invalid_ticket_state", "No re-analysis request is awaiting review."
            )
        route = responsible_route(ticket)
        permission = ROUTE_PERMISSIONS.get(route) if route is not None else None
        if permission is None or permission not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
        if actor.user_id in assigned_analyst_ids(ticket):
            raise AppError(
                403, "separation_of_duties", "Assigned analysts cannot decide re-analysis."
            )
        if not ticket.product_outcomes.customer_decisions:
            raise AppError(409, "decision_context_missing", "Customer decision is unavailable.")
        customer = ticket.product_outcomes.customer_decisions[-1]
        status = (
            ManagerReanalysisStatus.AGREED if agree else ManagerReanalysisStatus.REFERRED_TO_JIOC
        )
        target = (
            TicketState.ANALYST_IN_PROGRESS if agree else TicketState.JIOC_REANALYSIS_ADJUDICATION
        )
        _require_transition(ticket, target)
        decision = ManagerReanalysisDecision(
            uuid4(),
            ticket_id,
            customer.decision_id,
            status,
            rationale.strip(),
            actor.user_id,
            datetime.now(UTC),
        )
        outcomes = replace(
            ticket.product_outcomes,
            manager_decisions=(*ticket.product_outcomes.manager_decisions, decision),
        )
        proposed = _new_analysis_cycle(ticket, target) if agree else replace(ticket, state=target)
        return self._save(
            ticket,
            replace(
                proposed,
                product_outcomes=outcomes,
                timeline=(
                    *ticket.timeline,
                    timeline(
                        ticket_id,
                        actor.user_id,
                        "manager_reanalysis_agreed" if agree else "manager_reanalysis_referred",
                        "The manager agreed to re-analysis."
                        if agree
                        else "The manager referred the disagreement to a JIOC human.",
                    ),
                ),
            ),
            "manager_reanalysis_agreed" if agree else "manager_reanalysis_referred",
            actor,
        )

    def jioc_decision(
        self, actor: UserAccount, ticket_id: UUID, *, reanalyse: bool, rationale: str
    ) -> TicketRecord:
        if Permission.JIOC_RESOLVE_CUSTOMER_DISPUTE not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
        if len(rationale.strip()) < 3:
            raise AppError(422, "reason_required", "A JIOC rationale is required.")
        ticket = self._workflow_ticket(actor, ticket_id)
        if ticket.state != TicketState.JIOC_REANALYSIS_ADJUDICATION:
            raise AppError(409, "invalid_ticket_state", "No customer dispute is awaiting JIOC.")
        if not ticket.product_outcomes.manager_decisions:
            raise AppError(409, "decision_context_missing", "Manager decision is unavailable.")
        manager = ticket.product_outcomes.manager_decisions[-1]
        if (
            actor.user_id == ticket.requester_user_id
            or actor.user_id == manager.actor_user_id
            or actor.user_id in assigned_analyst_ids(ticket)
        ):
            raise AppError(403, "separation_of_duties", "An independent JIOC human is required.")
        status = JiocReanalysisStatus.REANALYSE if reanalyse else JiocReanalysisStatus.CLOSE
        target = (
            TicketState.ANALYST_IN_PROGRESS if reanalyse else TicketState.CLOSED_REANALYSIS_DECLINED
        )
        _require_transition(ticket, target)
        decision = JiocReanalysisDecision(
            uuid4(),
            ticket_id,
            manager.decision_id,
            status,
            rationale.strip(),
            actor.user_id,
            datetime.now(UTC),
        )
        outcomes = replace(
            ticket.product_outcomes,
            jioc_decisions=(*ticket.product_outcomes.jioc_decisions, decision),
        )
        proposed = (
            _new_analysis_cycle(ticket, target) if reanalyse else replace(ticket, state=target)
        )
        return self._save(
            ticket,
            replace(
                proposed,
                product_outcomes=outcomes,
                timeline=(
                    *ticket.timeline,
                    timeline(
                        ticket_id,
                        actor.user_id,
                        "jioc_reanalysis_ordered" if reanalyse else "jioc_reanalysis_declined",
                        "JIOC ordered re-analysis."
                        if reanalyse
                        else "JIOC closed the request without re-analysis.",
                    ),
                ),
            ),
            "jioc_reanalysis_ordered" if reanalyse else "jioc_reanalysis_declined",
            actor,
        )

    def _workflow_ticket(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        return self._tickets.tickets.get_workflow_ticket(
            actor,
            ticket_id,
            frozenset(
                {
                    Permission.RFA_REVIEW,
                    Permission.COLLECTION_REVIEW,
                    Permission.JIOC_RESOLVE_CUSTOMER_DISPUTE,
                }
            ),
        )

    def _save(
        self,
        expected: TicketRecord,
        proposed: TicketRecord,
        event: str,
        actor: UserAccount,
    ) -> TicketRecord:
        return self._tickets.mutations.save_audited_if_current(
            expected,
            proposed,
            event,
            actor,
            {"ticket_id": str(expected.ticket_id)},
        )


def responsible_route(ticket: TicketRecord) -> RoutingRoute | None:
    assignments = active_assignments(ticket)
    return assignments[-1].route if assignments else approved_route(ticket)


def _new_analysis_cycle(ticket: TicketRecord, target: TicketState) -> TicketRecord:
    _require_transition(ticket, target)
    return replace(
        ticket,
        state=target,
        work_packages=tuple(
            replace(package, status=WorkPackageStatus.PENDING) for package in ticket.work_packages
        ),
        manager_approved_manifest_hash=None,
        qc_reviewer_user_id=None,
        qc_claimed_at=None,
    )


def _require_transition(ticket: TicketRecord, target: TicketState) -> None:
    if not can_transition(ticket.state, target):
        raise AppError(409, "invalid_ticket_state", "Ticket cannot make that transition.")
