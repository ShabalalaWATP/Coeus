from dataclasses import replace
from uuid import UUID

from coeus.domain.enums import TicketState
from coeus.domain.search_metrics import RfiSearchMetrics
from coeus.domain.tickets import ProductOffer, ProductOfferStatus, TicketRecord

RFI_RESULT_SIGNAL_STATES = frozenset(
    {
        TicketState.RFI_SEARCH_INCOMPLETE,
        TicketState.RFI_NO_MATCH,
        TicketState.RFI_MATCH_OFFERED,
        TicketState.NEW_TASKING_CONSENT,
        TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED,
    }
)
RFI_OUTCOME_TIMELINE_EVENTS = frozenset(
    {
        "rfi_no_match",
        "rfi_search_incomplete",
        "product_offer_accepted",
        "product_offer_rejected",
    }
)


def project_rfi_result_signal(
    ticket: TicketRecord,
    visible_product_ids: frozenset[UUID],
    *,
    preserve_full: bool = False,
) -> TicketRecord:
    """Derive every Store-result signal from the caller-visible offer set."""
    if preserve_full or ticket.state not in RFI_RESULT_SIGNAL_STATES:
        return ticket
    offer_ids = frozenset(offer.product_id for offer in ticket.product_offers)
    full_offer_visibility = bool(offer_ids) and offer_ids.issubset(visible_product_ids)
    offers = tuple(
        offer for offer in ticket.product_offers if offer.product_id in visible_product_ids
    )
    metric = ticket.search_metrics[-1] if ticket.search_metrics else None
    state, outcome, assurance = _visible_decision(offers, metric)
    projected_metrics = ticket.search_metrics
    if metric is not None:
        accepted_product_id = (
            metric.accepted_product_id
            if metric.accepted_product_id in visible_product_ids
            else None
        )
        projected_metrics = (
            *ticket.search_metrics[:-1],
            replace(
                metric,
                candidate_count=0,
                offered_count=len(offers),
                rejected_count=sum(offer.status == ProductOfferStatus.REJECTED for offer in offers),
                accepted_product_id=accepted_product_id,
                outcome=outcome,
                assurance=assurance,
            ),
        )
    return replace(
        ticket,
        state=state,
        product_offers=offers,
        search_evidence=tuple(
            item for item in ticket.search_evidence if item.product_id in visible_product_ids
        ),
        search_metrics=projected_metrics,
        visible_product_matches=tuple(offer.title for offer in offers),
        disseminations=tuple(
            item for item in ticket.disseminations if item.product_id in visible_product_ids
        ),
        timeline=(
            ticket.timeline
            if full_offer_visibility
            else tuple(
                entry
                for entry in ticket.timeline
                if entry.event_type not in RFI_OUTCOME_TIMELINE_EVENTS
            )
        ),
    )


def _visible_decision(
    offers: tuple[ProductOffer, ...], metric: RfiSearchMetrics | None
) -> tuple[TicketState, str, str]:
    accepted_id = metric.accepted_product_id if metric is not None else None
    if accepted_id is not None and any(
        offer.product_id == accepted_id and offer.status == ProductOfferStatus.ACCEPTED
        for offer in offers
    ):
        return TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED, "offers", "assisted"
    if any(offer.status == ProductOfferStatus.OFFERED for offer in offers):
        return TicketState.RFI_MATCH_OFFERED, "offers", "assisted"
    complete = bool(
        offers
        and metric is not None
        and metric.coverage_status in {"complete", "legacy"}
        and metric.degraded_reason is None
    )
    if complete:
        return TicketState.NEW_TASKING_CONSENT, "no_match", "definitive"
    return TicketState.RFI_SEARCH_INCOMPLETE, "incomplete", "assisted"
