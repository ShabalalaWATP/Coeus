"""Deterministic demo tickets spanning the whole workflow (MOCK DATA ONLY).

Local-only: populates every queue (customer, JIOC, team, analyst, QC) and the
analytics dashboards on a fresh run. Tickets are assembled directly in their
target state from the same record builders the live services use, so each one
carries the sub-records its queue and panels expect. Stable IDs mean
re-seeding never duplicates.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.qc import FeedbackRequestStatus, FeedbackSubmission, QcDecision, QcDecisionStatus
from coeus.domain.store import StoreProduct
from coeus.domain.tickets import (
    ChatMessage,
    DraftProductAsset,
    IntakeDetails,
    ManagerRoutingDecisionStatus,
    MessageAuthor,
    ProductOffer,
    ProductOfferStatus,
    RoutingRoute,
    TicketRecord,
    TicketTimelineEntry,
    WorkPackageStatus,
)
from coeus.repositories.access import stable_seed_id
from coeus.repositories.demo_ticket_specs import SPECS, DemoTicketSpec
from coeus.services.analyst_records import assignment_record, draft_version, work_package_records
from coeus.services.prioritisation import with_assessment
from coeus.services.qc_records import (
    checklist_items,
    dissemination,
    feedback_request,
    indexed_product,
    qc_decision,
)
from coeus.services.routing_records import decision

_NOW = datetime.now(UTC)

_ANALYST_STATES = {
    TicketState.ANALYST_IN_PROGRESS,
    TicketState.MANAGER_APPROVAL,
    TicketState.QC_REVIEW,
    TicketState.REWORK_REQUIRED,
    TicketState.DISSEMINATION_READY,
    TicketState.CLOSED_DELIVERED,
}
_APPROVED_STATES = {TicketState.ANALYST_ASSIGNMENT} | _ANALYST_STATES
_DRAFT_STATES = {
    TicketState.MANAGER_APPROVAL,
    TicketState.QC_REVIEW,
    TicketState.DISSEMINATION_READY,
    TicketState.CLOSED_DELIVERED,
}
_DELIVERED_STATES = {TicketState.DISSEMINATION_READY, TicketState.CLOSED_DELIVERED}


def build_demo_tickets(
    users: dict[str, UserAccount], products: tuple[StoreProduct, ...]
) -> tuple[TicketRecord, ...]:
    published = tuple(p for p in products if p.metadata.status.value == "published")
    return tuple(_build(spec, index, users, published) for index, spec in enumerate(SPECS))


def _build(
    spec: DemoTicketSpec,
    index: int,
    users: dict[str, UserAccount],
    published: tuple[StoreProduct, ...],
) -> TicketRecord:
    requester = users[spec.requester]
    manager = users[
        "rfa.manager@example.test"
        if spec.route != RoutingRoute.CM
        else "collection.manager@example.test"
    ]
    analyst = users["analyst@example.test"]
    qc_manager = users["qc.manager@example.test"]
    ticket_id = stable_seed_id(f"demo-ticket-{spec.key}")
    created = _NOW - timedelta(hours=6 * index + 2)
    ticket = with_assessment(
        TicketRecord(
            ticket_id=ticket_id,
            reference=f"TCK-{101 + index:04d}",
            requester_user_id=requester.user_id,
            state=spec.state,
            intake=_intake(spec),
            messages=_messages(ticket_id, created),
            timeline=(_timeline(ticket_id, requester.user_id, created),),
            created_at=created,
            updated_at=created,
        )
    )
    if spec.state == TicketState.RFI_MATCH_OFFERED and published:
        ticket = replace(ticket, product_offers=(_offer(published[spec.product_index or 0]),))
    if spec.route is not None and spec.state in _APPROVED_STATES:
        ticket = _with_route(ticket, spec, manager, analyst)
    if spec.state in _DRAFT_STATES:
        ticket = _with_draft(ticket, analyst)
    if spec.state == TicketState.QC_REVIEW:
        ticket = _complete_packages(ticket)
    if spec.state in _DELIVERED_STATES and published:
        ticket = _with_delivery(ticket, spec, qc_manager, requester, published)
    if spec.state == TicketState.COLLECT_CHOICE:
        ticket = _with_collect_choice(ticket, spec, users["jioc.team@example.test"])
    return ticket


def _intake(spec: DemoTicketSpec) -> IntakeDetails:
    return IntakeDetails(
        title=spec.title,
        description=f"MOCK DATA ONLY request about {spec.area}.",
        operational_question=f"What should command know about {spec.area}?",
        area_or_region=spec.area,
        time_period_start="2026-06-01",
        time_period_end="2026-06-30",
        priority=spec.priority,
        deadline="End of week" if spec.priority == "urgent" else None,
        required_output_format=spec.output_format,
        customer_success_criteria="Give the duty officer a clear, actionable picture.",
        requesting_unit="Carrier Strike Group Atlas",
        intelligence_disciplines="IMINT, OSINT",
        supported_operation="Operation Harbour Sentinel" if spec.priority == "urgent" else None,
        urgency_justification="A posture decision is due this week."
        if spec.priority == "urgent"
        else None,
        confidence=1.0,
    )


def _messages(ticket_id: UUID, created: datetime) -> tuple[ChatMessage, ...]:
    return (
        ChatMessage(
            stable_seed_id(f"{ticket_id}-m1"),
            ticket_id,
            MessageAuthor.USER,
            "Hi Istari, I need a picture on this area.",
            created,
        ),
        ChatMessage(
            stable_seed_id(f"{ticket_id}-m2"),
            ticket_id,
            MessageAuthor.ASSISTANT,
            "Understood. I have captured the requirement.",
            created,
        ),
    )


def _timeline(ticket_id: UUID, user_id: UUID, created: datetime) -> TicketTimelineEntry:
    return TicketTimelineEntry(
        entry_id=stable_seed_id(f"{ticket_id}-t1"),
        ticket_id=ticket_id,
        event_type="ticket_created",
        body="Draft intake started.",
        actor_user_id=user_id,
        created_at=created,
    )


def _offer(product: StoreProduct) -> ProductOffer:
    meta = product.metadata
    return ProductOffer(
        product_id=product.product_id,
        title=meta.title,
        summary=meta.summary,
        product_type=meta.product_type,
        match_score=0.78,
        match_reasons=("full-text:region", "metadata:discipline"),
        classification_level=meta.classification_level,
        releasability=tuple(meta.releasability),
        region=meta.area_or_region,
        time_period_start=meta.time_period_start,
        time_period_end=meta.time_period_end,
        asset_types=("pdf",),
        offerable_to_user=True,
        status=ProductOfferStatus.OFFERED,
    )


def _with_route(
    ticket: TicketRecord, spec: DemoTicketSpec, manager: UserAccount, analyst: UserAccount
) -> TicketRecord:
    route = spec.route or RoutingRoute.RFA
    approved = decision(
        ticket.ticket_id,
        manager.user_id,
        route,
        ManagerRoutingDecisionStatus.APPROVED,
        "Collection not required; approved for analyst assignment."
        if route == RoutingRoute.RFA
        else "Collection required; routed to CM.",
        None,
    )
    ticket = replace(ticket, manager_decisions=(*ticket.manager_decisions, approved))
    if spec.state in _ANALYST_STATES:
        assignment = assignment_record(
            ticket.ticket_id, analyst.user_id, manager.user_id, route, "Maritime Assessment Cell"
        )
        packages = work_package_records(
            ticket.ticket_id, ("Review permitted products", "Draft the assessment")
        )
        ticket = replace(ticket, analyst_assignments=(assignment,), work_packages=packages)
    return ticket


def _complete_packages(ticket: TicketRecord) -> TicketRecord:
    return replace(
        ticket,
        work_packages=tuple(
            replace(package, status=WorkPackageStatus.COMPLETE) for package in ticket.work_packages
        ),
    )


def _with_draft(ticket: TicketRecord, analyst: UserAccount) -> TicketRecord:
    asset = DraftProductAsset(
        asset_id=stable_seed_id(f"{ticket.ticket_id}-draft-asset"),
        name="assessment-draft.pdf",
        asset_type="pdf",
        mime_type="application/pdf",
        size_bytes=512,
        sha256="d" * 64,
    )
    draft = draft_version(
        ticket.ticket_id,
        1,
        f"{ticket.intake.title} Draft",
        "MOCK DATA ONLY analyst draft.",
        "finished_output",
        "MOCK DATA ONLY. Assessment content prepared for review.",
        (asset,),
        analyst.user_id,
    )
    return _complete_packages(replace(ticket, draft_products=(draft,)))


def _with_delivery(
    ticket: TicketRecord,
    spec: DemoTicketSpec,
    qc_manager: UserAccount,
    requester: UserAccount,
    published: tuple[StoreProduct, ...],
) -> TicketRecord:
    product = published[(spec.product_index or 0) % len(published)]
    qc = _qc_decision(ticket.ticket_id, qc_manager.user_id)
    index_record = indexed_product(ticket.ticket_id, product.product_id)
    disseminated = dissemination(ticket.ticket_id, product.product_id, requester.user_id)
    request = replace(
        feedback_request(ticket.ticket_id, product.product_id, requester.user_id),
        status=FeedbackRequestStatus.SUBMITTED,
    )
    submission = FeedbackSubmission(
        submission_id=stable_seed_id(f"{ticket.ticket_id}-feedback"),
        request_id=request.request_id,
        ticket_id=ticket.ticket_id,
        product_id=product.product_id,
        requester_user_id=requester.user_id,
        rating=5 if spec.state == TicketState.CLOSED_DELIVERED else 4,
        comment="MOCK DATA ONLY: clear and actionable.",
        follow_up_requested=False,
        created_at=ticket.created_at,
    )
    return replace(
        ticket,
        qc_decisions=(qc,),
        product_index_records=(index_record,),
        disseminations=(disseminated,),
        feedback_requests=(request,),
        feedback_submissions=(submission,),
    )


def _qc_decision(ticket_id: UUID, reviewer_id: UUID) -> QcDecision:
    return qc_decision(
        ticket_id,
        QcDecisionStatus.APPROVED,
        "QC checklist complete.",
        reviewer_id,
        checklist_items({key: True for key in _CHECKLIST_KEYS}),
    )


def _with_collect_choice(
    ticket: TicketRecord, spec: DemoTicketSpec, jioc: UserAccount
) -> TicketRecord:
    approved = decision(
        ticket.ticket_id,
        jioc.user_id,
        RoutingRoute.CM,
        ManagerRoutingDecisionStatus.APPROVED,
        "Collection required; routed to CM.",
        None,
    )
    return replace(ticket, manager_decisions=(*ticket.manager_decisions, approved))


_CHECKLIST_KEYS = (
    "answers_customer_question",
    "sources_are_sufficient",
    "metadata_complete",
    "classification_checked",
    "releasability_checked",
    "acg_assignment_checked",
    "format_correct",
    "handling_caveats_applied",
    "manager_comments_resolved",
)
