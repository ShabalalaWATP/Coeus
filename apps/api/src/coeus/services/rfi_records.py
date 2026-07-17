from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.domain.agent_names import LEGACY_RFI_SEARCH_AGENT, RFI_SEARCH_AGENT
from coeus.domain.search_metrics import RfiSearchMetrics
from coeus.domain.tickets import (
    AgentRun,
    AgentRunStatus,
    ProductOffer,
    ProductOfferStatus,
    TicketRecord,
    TicketTimelineEntry,
)


def active_offer(ticket: TicketRecord, product_id: UUID) -> ProductOffer:
    for offer in ticket.product_offers:
        if offer.product_id == product_id and offer.status == ProductOfferStatus.OFFERED:
            return offer
    raise AppError(404, "product_offer_not_found", "Product offer was not found.")


def set_offer_status(
    offers: tuple[ProductOffer, ...],
    product_id: UUID,
    status: ProductOfferStatus,
    rejection_reason: str | None = None,
) -> tuple[ProductOffer, ...]:
    return tuple(
        replace(offer, status=status, rejection_reason=rejection_reason)
        if offer.product_id == product_id
        else offer
        for offer in offers
    )


def complete_agent_run(
    ticket: TicketRecord, summary: str, now: datetime
) -> tuple[tuple[AgentRun, ...], UUID]:
    for run in ticket.agent_runs:
        if (
            run.agent_name in {RFI_SEARCH_AGENT, LEGACY_RFI_SEARCH_AGENT}
            and run.status == AgentRunStatus.QUEUED
        ):
            updated = replace(
                run,
                agent_name=RFI_SEARCH_AGENT,
                status=AgentRunStatus.COMPLETED,
                summary=summary,
                created_at=now,
            )
            runs = tuple(
                updated if item.run_id == run.run_id else item for item in ticket.agent_runs
            )
            return runs, run.run_id
    run = AgentRun(
        uuid4(),
        ticket.ticket_id,
        RFI_SEARCH_AGENT,
        AgentRunStatus.COMPLETED,
        summary,
        (),
        now,
    )
    return (*ticket.agent_runs, run), run.run_id


def accepted_metric(ticket: TicketRecord, product_id: UUID) -> RfiSearchMetrics:
    return replace(_latest_metric(ticket), accepted_product_id=product_id)


def rejected_metric(ticket: TicketRecord, offers: tuple[ProductOffer, ...]) -> RfiSearchMetrics:
    return replace(
        _latest_metric(ticket),
        rejected_count=sum(offer.status == ProductOfferStatus.REJECTED for offer in offers),
    )


def _latest_metric(ticket: TicketRecord) -> RfiSearchMetrics:
    if not ticket.search_metrics:
        raise AppError(
            409,
            "search_metrics_missing",
            "Search results are unavailable. Run the search again.",
        )
    return ticket.search_metrics[-1]


def timeline(
    ticket_id: UUID, actor_user_id: UUID, event_type: str, body: str
) -> TicketTimelineEntry:
    return TicketTimelineEntry(
        uuid4(),
        ticket_id,
        event_type,
        body,
        actor_user_id,
        datetime.now(UTC),
    )


def run_summary(offer_count: int, candidate_count: int) -> str:
    if offer_count:
        return (
            f"Search completed with {offer_count} offer(s) from "
            f"{candidate_count} permitted candidate(s)."
        )
    return (
        "No permitted existing product exceeded the offer threshold from "
        f"{candidate_count} candidate(s)."
    )
