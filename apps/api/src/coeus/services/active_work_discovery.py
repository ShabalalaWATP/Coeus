"""Durable customer decisions for matching in-progress work."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from coeus.core.errors import AppError
from coeus.domain.auth import AuthenticatedSession, SessionRecord, UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.tickets import TicketRecord
from coeus.domain.work_discovery import ActiveWorkOffer
from coeus.domain.workflow_authority import WorkflowCommitAuthority
from coeus.services.similar_request_scoring import OPEN_SIMILARITY_STATES, SimilarRequestMatch
from coeus.services.similar_requests import SimilarRequestService
from coeus.services.ticket_records import is_owner, timeline
from coeus.services.tickets import TicketServices


class ActiveWorkDiscoveryService:
    def __init__(self, tickets: TicketServices, similar: SimilarRequestService) -> None:
        self._tickets = tickets
        self._similar = similar

    def discover(self, authenticated: AuthenticatedSession, ticket_id: UUID) -> TicketRecord:
        return self._discover(authenticated.user, authenticated.session, ticket_id)

    def discover_automated(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        """Run trusted outbox discovery without an end-user session requirement."""
        return self._discover(actor, None, ticket_id)

    def _discover(
        self,
        actor: UserAccount,
        session: SessionRecord | None,
        ticket_id: UUID,
    ) -> TicketRecord:
        ticket = self._tickets.tickets.get_visible_ticket(actor, ticket_id)
        if ticket.state == TicketState.ACTIVE_WORK_REVIEW:
            return ticket
        if ticket.state not in {
            TicketState.NEW_TASKING_CONSENT,
            TicketState.ACTIVE_WORK_SEARCH_INCOMPLETE,
        }:
            return ticket
        if ticket.state == TicketState.NEW_TASKING_CONSENT and any(
            item.event_type == "active_work_search_completed" for item in ticket.timeline
        ):
            return ticket
        now = datetime.now(UTC)
        matches = self._similar.customer_matches(actor, ticket_id)
        offers = tuple(_offer(match, now) for match in matches)
        target_state = TicketState.ACTIVE_WORK_REVIEW if offers else TicketState.NEW_TASKING_CONSENT
        return self._tickets.mutations.save_authorised_audited_if_current(
            ticket,
            replace(
                ticket,
                state=target_state,
                active_work_offers=offers,
                timeline=(
                    *ticket.timeline,
                    timeline(
                        ticket.ticket_id,
                        actor.user_id,
                        "active_work_search_completed",
                        _discovery_message(len(offers)),
                    ),
                ),
            ),
            "active_work_search_completed",
            WorkflowCommitAuthority(actor, session, frozenset()),
            {"ticket_id": str(ticket.ticket_id), "offered_count": str(len(offers))},
            (
                (
                    "similar_request_notified",
                    self._similar.notice_metadata(ticket.ticket_id, matches),
                ),
            )
            if matches
            else (),
        )

    def record_incomplete(
        self,
        authenticated: AuthenticatedSession,
        ticket_id: UUID,
        reason: str,
    ) -> TicketRecord:
        actor = authenticated.user
        ticket = self._tickets.tickets.get_visible_ticket(actor, ticket_id)
        if ticket.state == TicketState.ACTIVE_WORK_SEARCH_INCOMPLETE:
            return ticket
        if ticket.state != TicketState.NEW_TASKING_CONSENT:
            return ticket
        return self._tickets.mutations.save_authorised_audited_if_current(
            ticket,
            replace(
                ticket,
                state=TicketState.ACTIVE_WORK_SEARCH_INCOMPLETE,
                timeline=(
                    *ticket.timeline,
                    timeline(
                        ticket.ticket_id,
                        actor.user_id,
                        "active_work_search_incomplete",
                        "The in-progress work check did not complete. Retry is required.",
                    ),
                ),
            ),
            "active_work_search_incomplete",
            WorkflowCommitAuthority(actor, authenticated.session, frozenset()),
            {"ticket_id": str(ticket.ticket_id), "reason": reason},
        )

    def offers(self, actor: UserAccount, ticket_id: UUID) -> tuple[SimilarRequestMatch, ...]:
        source = self._tickets.tickets.get_visible_ticket(actor, ticket_id)
        if source.state != TicketState.ACTIVE_WORK_REVIEW:
            return ()
        visible: list[SimilarRequestMatch] = []
        for offer in source.active_work_offers:
            if offer.status != "offered":
                continue
            try:
                target = self._tickets.tickets.get_visible_ticket(actor, offer.ticket_id)
            except AppError:
                continue
            if target.state not in OPEN_SIMILARITY_STATES:
                continue
            visible.append(_match(offer, source))
        return tuple(visible)

    def join(self, actor: UserAccount, ticket_id: UUID, related_id: UUID) -> TicketRecord:
        source = self._tickets.tickets.get_visible_ticket(actor, ticket_id)
        if not is_owner(actor, source):
            raise AppError(404, "ticket_not_found", "Ticket was not found.")
        if (
            source.state == TicketState.CLOSED_JOINED_EXISTING_WORK
            and source.duplicate_of_ticket_id == related_id
        ):
            return self._tickets.tickets.get_visible_ticket(actor, related_id)
        if source.state != TicketState.ACTIVE_WORK_REVIEW:
            raise AppError(409, "invalid_ticket_state", "No active-work decision is pending.")
        offer = next(
            (
                item
                for item in source.active_work_offers
                if item.ticket_id == related_id and item.status == "offered"
            ),
            None,
        )
        if offer is None:
            raise AppError(404, "similar_request_not_found", "Similar request was not found.")
        target = self._tickets.tickets.get_visible_ticket(actor, related_id)
        if target.state not in OPEN_SIMILARITY_STATES:
            raise AppError(409, "similar_request_closed", "The similar request is no longer open.")
        now = datetime.now(UTC)
        source_offers = tuple(
            replace(item, status="accepted", decided_at=now)
            if item.ticket_id == related_id
            else replace(item, status="rejected", decided_at=now)
            for item in source.active_work_offers
        )
        source_proposed = replace(
            source,
            state=TicketState.CLOSED_JOINED_EXISTING_WORK,
            duplicate_of_ticket_id=target.ticket_id,
            related_ticket_ids=_append(source.related_ticket_ids, target.ticket_id),
            active_work_offers=source_offers,
            timeline=(
                *source.timeline,
                timeline(
                    source.ticket_id,
                    actor.user_id,
                    "active_work_joined",
                    f"Joined existing work {target.reference}.",
                ),
            ),
        )
        target_proposed = replace(
            target,
            related_ticket_ids=_append(target.related_ticket_ids, source.ticket_id),
        )
        self._tickets.mutations.save_pair_audited(
            (source, target),
            (source_proposed, target_proposed),
            "active_work_joined",
            actor,
            {"ticket_id": str(source.ticket_id), "canonical_ticket_id": str(target.ticket_id)},
        )
        return target

    def continue_new_tasking(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        source = self._owned_review(actor, ticket_id)
        now = datetime.now(UTC)
        return self._tickets.mutations.save_audited_if_current(
            source,
            replace(
                source,
                state=TicketState.NEW_TASKING_CONSENT,
                active_work_offers=tuple(
                    replace(item, status="rejected", decided_at=now)
                    for item in source.active_work_offers
                ),
                timeline=(
                    *source.timeline,
                    timeline(
                        source.ticket_id,
                        actor.user_id,
                        "active_work_declined",
                        "Requester declined the offered in-progress work.",
                    ),
                ),
            ),
            "active_work_declined",
            actor,
            {"ticket_id": str(source.ticket_id)},
        )

    def _owned_review(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        source = self._tickets.tickets.get_visible_ticket(actor, ticket_id)
        if not is_owner(actor, source):
            raise AppError(404, "ticket_not_found", "Ticket was not found.")
        if source.state != TicketState.ACTIVE_WORK_REVIEW:
            raise AppError(409, "invalid_ticket_state", "No active-work decision is pending.")
        return source


def _offer(match: SimilarRequestMatch, now: datetime) -> ActiveWorkOffer:
    return ActiveWorkOffer(
        ticket_id=match.ticket_id,
        reference=match.reference,
        title=match.title,
        state=match.state.value,
        score=match.score,
        reasons=match.reasons,
        request_kind=match.request_kind,
        approved_route=match.approved_route,
        assigned_team=match.assigned_team,
        requesting_unit=match.requesting_unit,
        supported_operation=match.supported_operation,
        time_period_start=match.time_period_start,
        time_period_end=match.time_period_end,
        status="offered",
        created_at=now,
    )


def _match(offer: ActiveWorkOffer, source: TicketRecord) -> SimilarRequestMatch:
    return SimilarRequestMatch(
        ticket_id=offer.ticket_id,
        reference=offer.reference,
        title=offer.title,
        state=TicketState(offer.state),
        score=offer.score,
        reasons=offer.reasons,
        already_linked=offer.ticket_id in source.related_ticket_ids,
        already_marked_duplicate=source.duplicate_of_ticket_id == offer.ticket_id,
        request_kind=offer.request_kind,
        approved_route=offer.approved_route,
        assigned_team=offer.assigned_team,
        requesting_unit=offer.requesting_unit,
        supported_operation=offer.supported_operation,
        time_period_start=offer.time_period_start,
        time_period_end=offer.time_period_end,
    )


def _append(values: tuple[UUID, ...], value: UUID) -> tuple[UUID, ...]:
    return values if value in values else (*values, value)


def _discovery_message(count: int) -> str:
    if count:
        return f"Found {count} authorised matching in-progress request(s)."
    return "No authorised matching in-progress requests were found."
