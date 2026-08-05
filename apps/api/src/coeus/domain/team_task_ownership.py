"""Canonical receiving-team ownership for one ticket workflow leg."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from coeus.domain.organisation_validation import aware, optional_text, text_value


class WorkflowLeg(StrEnum):
    RFA = "rfa"
    CM_COLLECTION = "cm_collection"
    CM_ANALYSIS = "cm_analysis"
    QC = "qc"


class TeamTaskOwnershipState(StrEnum):
    TRIAGE = "triage"
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OWNERSHIP_UNRESOLVED = "ownership_unresolved"


@dataclass(frozen=True)
class AssignmentOwnershipIntent:
    """Canonical ownership requested by an analyst assignment mutation."""

    owning_unit_id: UUID
    workflow_leg: WorkflowLeg
    manager_user_id: UUID
    history_reference: UUID
    target_date: date | None = None
    provenance: str = "atomic_assignment_projection"

    def __post_init__(self) -> None:
        text_value(self.provenance, "provenance", 120)


def delivery_route_for_leg(workflow_leg: WorkflowLeg) -> str:
    if workflow_leg is WorkflowLeg.RFA:
        return "rfa"
    if workflow_leg in {WorkflowLeg.CM_COLLECTION, WorkflowLeg.CM_ANALYSIS}:
        return "cm"
    return "qc"


@dataclass(frozen=True)
class TeamTaskOwnership:
    ownership_id: UUID
    ticket_id: UUID
    workflow_leg: WorkflowLeg
    owning_unit_id: UUID
    manager_user_id: UUID | None
    state: TeamTaskOwnershipState
    topology_revision_id: UUID
    capability_policy_version: int
    version: int
    history_reference: UUID
    provenance: str
    created_at: datetime
    accepted_at: datetime | None = None
    target_date: date | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        aware(self.created_at, "created_at")
        aware(self.accepted_at, "accepted_at")
        text_value(self.provenance, "provenance", 120)
        optional_text(self.reason, "reason", 500)
        if self.capability_policy_version < 1:
            raise ValueError("capability_policy_version must be positive")
        if self.version < 1:
            raise ValueError("version must be positive")
        accepted_states = {
            TeamTaskOwnershipState.ACCEPTED,
            TeamTaskOwnershipState.ACTIVE,
            TeamTaskOwnershipState.COMPLETED,
        }
        if (self.state in accepted_states) != (self.accepted_at is not None):
            raise ValueError("accepted ownership states require accepted_at")
        if self.accepted_at is not None and self.accepted_at < self.created_at:
            raise ValueError("accepted_at cannot precede created_at")
