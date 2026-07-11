"""Static specs for the local demo tickets (MOCK DATA ONLY).

Data only; the builder lives in ``demo_tickets.py``. One spec per target
workflow state so every queue is populated on a fresh local run.
"""

from dataclasses import dataclass

from coeus.domain.enums import TicketState
from coeus.domain.tickets import RoutingRoute

_U = "user@example.test"
_C = "colleague@example.test"
_RFA = RoutingRoute.RFA
_CM = RoutingRoute.CM


@dataclass(frozen=True)
class DemoTicketSpec:
    key: str
    requester: str
    state: TicketState
    title: str
    area: str
    output_format: str
    priority: str
    route: RoutingRoute | None = None
    product_index: int | None = None


SPECS: tuple[DemoTicketSpec, ...] = (
    DemoTicketSpec(
        "draft",
        _U,
        TicketState.DRAFT_INTAKE,
        "Baltic Ferry Disruption Picture",
        "Baltic Sea",
        "briefing note",
        "routine",
    ),
    DemoTicketSpec(
        "info",
        _C,
        TicketState.INFO_REQUIRED,
        "Sahel Convoy Threat Update",
        "Sahel, Africa",
        "assessment report",
        "priority",
    ),
    DemoTicketSpec(
        "searching",
        _U,
        TicketState.RFI_SEARCHING,
        "Arctic Shipping Lane Activity",
        "Arctic Circle",
        "assessment report",
        "routine",
    ),
    DemoTicketSpec(
        "offered",
        _U,
        TicketState.RFI_MATCH_OFFERED,
        "Eastern Europe Cyber Posture",
        "Eastern Europe",
        "assessment report",
        "priority",
        product_index=0,
    ),
    DemoTicketSpec(
        "nomatch",
        _U,
        TicketState.RFI_NO_MATCH,
        "South China Sea Reef Works",
        "South China Sea",
        "imagery report",
        "priority",
    ),
    DemoTicketSpec(
        "jioc-rfa",
        _U,
        TicketState.JIOC_REVIEW,
        "Levant Escalation Indicators",
        "Eastern Mediterranean",
        "assessment report",
        "urgent",
    ),
    DemoTicketSpec(
        "jioc-cm",
        _C,
        TicketState.JIOC_REVIEW,
        "North Atlantic Emitter Collection",
        "North Atlantic approaches",
        "collection plan",
        "priority",
    ),
    DemoTicketSpec(
        "collect",
        _U,
        TicketState.COLLECT_CHOICE,
        "Kaliningrad Corridor Sensor Tasking",
        "Kaliningrad corridor",
        "collection plan",
        "urgent",
        route=_CM,
    ),
    DemoTicketSpec(
        "assign-rfa",
        _U,
        TicketState.ANALYST_ASSIGNMENT,
        "Gulf of Guinea Piracy Assessment",
        "Gulf of Guinea",
        "assessment report",
        "priority",
        route=_RFA,
    ),
    DemoTicketSpec(
        "assign-cm",
        _C,
        TicketState.ANALYST_ASSIGNMENT,
        "Western Pacific Naval Movements",
        "Western Pacific",
        "collection plan",
        "priority",
        route=_CM,
    ),
    DemoTicketSpec(
        "in-progress",
        _U,
        TicketState.ANALYST_IN_PROGRESS,
        "Andean Trafficking Network Review",
        "Andean region",
        "assessment report",
        "routine",
        route=_RFA,
    ),
    DemoTicketSpec(
        "approval",
        _C,
        TicketState.MANAGER_APPROVAL,
        "High North Posture Assessment",
        "Arctic Circle",
        "assessment report",
        "priority",
        route=_RFA,
    ),
    DemoTicketSpec(
        "qc",
        _U,
        TicketState.QC_REVIEW,
        "Critical Infrastructure Phishing Review",
        "North America",
        "assessment report",
        "priority",
        route=_RFA,
    ),
    DemoTicketSpec(
        "rework",
        _C,
        TicketState.REWORK_REQUIRED,
        "Maritime Insurance Risk Brief",
        "North Atlantic approaches",
        "briefing note",
        "routine",
        route=_RFA,
    ),
    DemoTicketSpec(
        "delivered",
        _U,
        TicketState.DISSEMINATION_READY,
        "Eastern Europe Grid Threat Brief",
        "Eastern Europe",
        "assessment report",
        "urgent",
        route=_RFA,
        product_index=1,
    ),
    DemoTicketSpec(
        "closed",
        _C,
        TicketState.CLOSED_DELIVERED,
        "Arctic Route Ice and Traffic Brief",
        "Arctic Circle",
        "assessment report",
        "priority",
        route=_RFA,
        product_index=2,
    ),
    DemoTicketSpec(
        "accepted",
        _U,
        TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED,
        "Existing Maritime Risk Digest",
        "North Atlantic approaches",
        "briefing note",
        "routine",
        product_index=3,
    ),
    DemoTicketSpec(
        "cancelled",
        _C,
        TicketState.CANCELLED,
        "Withdrawn Regional Request",
        "Middle East",
        "assessment report",
        "routine",
    ),
)
