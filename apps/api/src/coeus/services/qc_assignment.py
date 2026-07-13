"""Atomic assigned-reviewer ownership for the shared Quality Control queue."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.qc import QcClaimStatus
from coeus.domain.qc_assignment import active_qc_reviewer_id, qc_claim_status
from coeus.domain.teams import TeamKind, team_member_ids
from coeus.domain.tickets import TicketRecord
from coeus.repositories.teams import TeamRepository
from coeus.services.prioritisation import priority_sort_key
from coeus.services.ticket_records import timeline
from coeus.services.tickets import TicketServices

QC_READ_PERMISSIONS = frozenset({Permission.QC_REVIEW})
QC_DETAIL_STATES = frozenset(
    {
        TicketState.QC_REVIEW,
        TicketState.DISSEMINATION_READY,
        TicketState.REWORK_REQUIRED,
    }
)


@dataclass(frozen=True)
class QcQueueItem:
    ticket_id: UUID
    reference: str
    state: TicketState
    claim_status: QcClaimStatus


@dataclass(frozen=True)
class QcQueueView:
    items: tuple[QcQueueItem, ...]
    assigned_products: tuple[TicketRecord, ...]


class QcAssignmentService:
    def __init__(self, tickets: TicketServices, teams: TeamRepository) -> None:
        self._tickets = tickets
        self._teams = teams

    def queue(self, actor: UserAccount) -> QcQueueView:
        self.require_eligible_actor(actor)
        queued = (
            ticket
            for ticket in self._tickets.tickets.list_workflow_tickets(actor, QC_READ_PERMISSIONS)
            if ticket.state == TicketState.QC_REVIEW
        )
        ordered = tuple(sorted(queued, key=priority_sort_key))
        return QcQueueView(
            items=tuple(
                QcQueueItem(
                    ticket.ticket_id,
                    ticket.reference,
                    ticket.state,
                    qc_claim_status(ticket, actor.user_id),
                )
                for ticket in ordered
            ),
            assigned_products=tuple(
                ticket for ticket in ordered if active_qc_reviewer_id(ticket) == actor.user_id
            ),
        )

    def details(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        self.require_eligible_actor(actor)
        ticket = self._get_ticket(actor, ticket_id)
        if ticket.state not in QC_DETAIL_STATES:
            raise self._not_found()
        if ticket.state == TicketState.DISSEMINATION_READY:
            self._ensure_historical_reviewer(actor, ticket)
        else:
            self._ensure_assigned(actor, ticket)
        self.ensure_separation_of_duties(actor, ticket)
        return ticket

    def claim(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        self.require_eligible_actor(actor)
        ticket = self._get_ticket(actor, ticket_id)
        if ticket.state != TicketState.QC_REVIEW:
            raise AppError(409, "invalid_ticket_state", "Ticket is not awaiting QC review.")
        self.ensure_separation_of_duties(actor, ticket)
        reviewer_id = active_qc_reviewer_id(ticket)
        if reviewer_id == actor.user_id:
            return ticket
        if reviewer_id is not None:
            raise self._already_claimed()
        proposed = replace(
            ticket,
            qc_reviewer_user_id=actor.user_id,
            qc_claimed_at=datetime.now(UTC),
            timeline=(
                *ticket.timeline,
                timeline(ticket.ticket_id, actor.user_id, "qc_claimed", "QC review claimed."),
            ),
        )
        try:
            return self._tickets.mutations.save_audited_if_current(
                ticket, proposed, "qc_claimed", actor, {"ticket_id": str(ticket_id)}
            )
        except AppError as exc:
            if exc.code != "ticket_changed":
                raise
            current = self._get_ticket(actor, ticket_id)
            if active_qc_reviewer_id(current) == actor.user_id:
                return current
            raise self._already_claimed() from exc

    def release(self, actor: UserAccount, ticket_id: UUID) -> None:
        self._require_permission(actor, Permission.QC_REVIEW)
        ticket = self._get_ticket(actor, ticket_id)
        self._ensure_assigned(actor, ticket)
        proposed = replace(
            ticket,
            qc_reviewer_user_id=None,
            qc_claimed_at=None,
            timeline=(
                *ticket.timeline,
                timeline(
                    ticket.ticket_id,
                    actor.user_id,
                    "qc_claim_released",
                    "QC claim released.",
                ),
            ),
        )
        self._tickets.mutations.save_audited_if_current(
            ticket,
            proposed,
            "qc_claim_released",
            actor,
            {"ticket_id": str(ticket_id)},
        )

    def claim_for_action(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        ticket = self.claim(actor, ticket_id)
        self._ensure_assigned(actor, ticket)
        return ticket

    def require_eligible_actor(self, actor: UserAccount) -> None:
        self._require_permission(actor, Permission.QC_REVIEW)
        if not actor.is_active or RoleName.QUALITY_CONTROL_MANAGER not in actor.roles:
            raise AppError(403, "forbidden", "Permission denied.")
        eligible = any(
            team.is_active and team.kind == TeamKind.QC and actor.user_id in team_member_ids(team)
            for team in self._teams.list_teams()
        )
        if not eligible:
            raise AppError(403, "forbidden", "Permission denied.")

    @staticmethod
    def ensure_separation_of_duties(actor: UserAccount, ticket: TicketRecord) -> None:
        authored = any(draft.created_by_user_id == actor.user_id for draft in ticket.draft_products)
        assigned = any(
            assignment.active and assignment.analyst_user_id == actor.user_id
            for assignment in ticket.analyst_assignments
        )
        if authored or assigned:
            raise AppError(403, "separation_of_duties", "Reviewers cannot review their own work.")

    def _get_ticket(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        return self._tickets.tickets.get_workflow_ticket(actor, ticket_id, QC_READ_PERMISSIONS)

    @staticmethod
    def _ensure_assigned(actor: UserAccount, ticket: TicketRecord) -> None:
        if active_qc_reviewer_id(ticket) != actor.user_id:
            raise QcAssignmentService._not_found()

    @staticmethod
    def _ensure_historical_reviewer(actor: UserAccount, ticket: TicketRecord) -> None:
        if ticket.qc_reviewer_user_id != actor.user_id:
            raise QcAssignmentService._not_found()

    @staticmethod
    def _require_permission(actor: UserAccount, permission: Permission) -> None:
        if permission not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")

    @staticmethod
    def _already_claimed() -> AppError:
        return AppError(409, "qc_already_claimed", "Another reviewer has claimed this product.")

    @staticmethod
    def _not_found() -> AppError:
        return AppError(404, "product_not_found", "QC product was not found.")
