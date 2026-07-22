"""Allowlisted customer history derived from the operational ticket record."""

from dataclasses import replace

from coeus.domain.tickets import ClarificationRequest, TicketRecord, TicketTimelineEntry

PUBLIC_EVENT_COPY = {
    "ticket_created": "Draft request started.",
    "intake_updated": "Requirement details updated.",
    "attachment_added": "Supporting information added.",
    "ticket_submitted": "Request submitted.",
    "search_started": "Search of authorised information started.",
    "rfi_search_completed": "Search completed.",
    "rfi_no_match": "No existing product matched this request.",
    "rfi_search_incomplete": "Search needs to be retried.",
    "product_offer_accepted": "An existing product was accepted.",
    "product_offer_rejected": "A suggested product was not accepted.",
    "active_work_search_completed": "Search of related active work completed.",
    "active_work_search_incomplete": "Search of related work needs to be retried.",
    "active_work_offered": "Related work is available to review.",
    "active_work_declined": "Related work was not joined.",
    "active_work_joined": "The request joined existing work.",
    "similar_request_joined": "The request joined existing work.",
    "tasking_confirmed": "Requester confirmed new tasking; queued for JIOC routing.",
    "tasking_declined": (
        "The search did not answer the question and the requester declined new tasking."
    ),
    "no_match_tasking_confirmed": "New tasking was approved.",
    "no_match_tasking_declined": "New tasking was declined.",
    "jioc_agent_route_applied": "The request was routed to a delivery team.",
    "jioc_agent_clarification_requested": "More information is required.",
    "customer_clarification_sent": "A clarification question was sent.",
    "information_added": "Additional information was supplied.",
    "route_assessment_resumed": "Routing resumed after clarification.",
    "collect_choice_requested": "A collection output choice is required.",
    "collect_choice_recorded": "The collection output choice was recorded.",
    "analyst_assigned": "The request was assigned to a delivery team.",
    "analyst_reassigned": "The delivery team assignment was updated.",
    "submitted_to_manager": "The draft moved to team review.",
    "manager_approved": "Team review completed.",
    "manager_returned_rework": "The draft returned for further work.",
    "submitted_to_qc": "The draft moved to quality review.",
    "qc_agent_preflight_completed": "Automated quality preflight completed.",
    "qc_approved": "Human quality review approved the product.",
    "qc_rejected": "Human quality review returned the product for rework.",
    "forwarded_to_rfa": "Collection completed and assessment work started.",
    "product_released": "The product was released.",
    "product_disseminated": "The product is ready for the customer.",
    "customer_notified": "The customer was notified.",
    "delivery_confirmed": "Delivery was confirmed.",
    "accepted": "The released product was accepted as meeting the requirement.",
    "rejected": "The released product was returned with an explanation.",
    "manager_reanalysis_agreed": "The team manager agreed to further analysis.",
    "manager_reanalysis_referred": "The decision was referred to JIOC.",
    "jioc_reanalysis_ordered": "JIOC ordered further analysis.",
    "jioc_reanalysis_declined": "JIOC closed the request after review.",
    "ticket_cancelled": "The request was cancelled.",
    "conversation_reopened": "The drafting conversation was reopened.",
    "collaborator_added": "A collaborator was added.",
    "collaborator_removed": "A collaborator was removed.",
}


def customer_timeline(ticket: TicketRecord) -> tuple[TicketTimelineEntry, ...]:
    return tuple(
        replace(
            entry,
            body=PUBLIC_EVENT_COPY[entry.event_type],
            actor_user_id=ticket.requester_user_id,
        )
        for entry in ticket.timeline
        if entry.event_type in PUBLIC_EVENT_COPY
    )


def customer_clarifications(
    ticket: TicketRecord,
) -> tuple[ClarificationRequest, ...]:
    return tuple(
        replace(item, reason="More information is needed to continue safely.")
        for item in ticket.clarification_requests
    )
