"""Submit a request and automatically resolve its first discovery outcome."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from coeus.application.ports.admission import ResourceAdmission
from coeus.core.async_work import run_bounded_search
from coeus.core.errors import AppError
from coeus.core.logging import get_logger
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.search_metrics import RfiSearchMetrics
from coeus.domain.tickets import TicketRecord
from coeus.services.active_work_discovery import ActiveWorkDiscoveryService
from coeus.services.rfi_ranking import query_text
from coeus.services.rfi_records import complete_agent_run, timeline
from coeus.services.rfi_search import RfiSearchService
from coeus.services.tickets import TicketServices

logger = get_logger(__name__)


class RequestSubmissionService:
    """Own the bounded submission-to-discovery application transaction."""

    def __init__(
        self,
        tickets: TicketServices,
        rfi_search: RfiSearchService,
        active_work: ActiveWorkDiscoveryService,
        admission: ResourceAdmission,
        automatic_discovery_enabled: bool = True,
        active_work_offers_enabled: bool = True,
    ) -> None:
        self._tickets = tickets
        self._rfi_search = rfi_search
        self._active_work = active_work
        self._admission = admission
        self._automatic_discovery_enabled = automatic_discovery_enabled
        self._active_work_offers_enabled = active_work_offers_enabled

    async def submit(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        submitted = self._tickets.tickets.submit(actor, ticket_id)
        if not self._automatic_discovery_enabled:
            return submitted
        try:
            with self._admission.reserve(actor.user_id):
                result = await run_bounded_search(self._rfi_search.run, actor, ticket_id)
            if (
                result.ticket.state == TicketState.NEW_TASKING_CONSENT
                and self._active_work_offers_enabled
            ):
                return self._active_work.discover(actor, ticket_id)
            return result.ticket
        except Exception as exc:
            logger.exception(
                "automatic_request_discovery_failed",
                extra={"ticket_id": str(ticket_id), "error": type(exc).__name__},
            )
            reason = exc.code if isinstance(exc, AppError) else "search_failed"
            return self._record_incomplete(actor, ticket_id, reason)

    def _record_incomplete(self, actor: UserAccount, ticket_id: UUID, reason: str) -> TicketRecord:
        ticket = self._tickets.tickets.get_visible_ticket(actor, ticket_id)
        if ticket.state == TicketState.NEW_TASKING_CONSENT:
            return self._active_work.record_incomplete(actor, ticket_id, reason)
        if ticket.state != TicketState.RFI_SEARCHING:
            return ticket
        now = datetime.now(UTC)
        summary = "Automatic discovery did not complete. Retry is required."
        agent_runs, run_id = complete_agent_run(ticket, summary, now)
        metric = RfiSearchMetrics(
            run_id=run_id,
            query=query_text(ticket.intake),
            candidate_count=0,
            offered_count=0,
            rejected_count=0,
            accepted_product_id=None,
            created_at=now,
            degraded_reason=reason,
            outcome="incomplete",
            assurance="assisted",
            coverage_status="partial",
        )
        return self._tickets.mutations.save_audited_if_current(
            ticket,
            replace(
                ticket,
                state=TicketState.RFI_SEARCH_INCOMPLETE,
                agent_runs=agent_runs,
                search_metrics=(*ticket.search_metrics, metric),
                timeline=(
                    *ticket.timeline,
                    timeline(
                        ticket.ticket_id,
                        actor.user_id,
                        "rfi_search_incomplete",
                        "Search did not complete. Retry before deciding on new tasking.",
                    ),
                ),
            ),
            "rfi_search_incomplete",
            actor,
            {"ticket_id": str(ticket.ticket_id), "reason": reason},
        )
