"""Atomic organisation reconciliation plan records."""

from dataclasses import dataclass
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from coeus.domain.organisation import (
    OrganisationReconciliationCheckpoint,
    OrganisationReconciliationFinding,
    OrganisationTopologyRevision,
    OrganisationUnit,
    ReconciliationStatus,
    TeamCapabilityCoverage,
    TeamDeliveryProfile,
    TeamMembership,
)

PROJECTION_ACTOR_ID = uuid5(NAMESPACE_URL, "coeus-organisation-v1:system-shadow-reconciler")


@dataclass(frozen=True)
class OrganisationReconciliationPlan:
    checkpoint: OrganisationReconciliationCheckpoint
    actor_user_id: UUID
    effective_at: datetime
    units: tuple[tuple[OrganisationUnit, OrganisationTopologyRevision], ...]
    delivery_profiles: tuple[TeamDeliveryProfile, ...]
    capability_coverage: tuple[TeamCapabilityCoverage, ...]
    memberships: tuple[TeamMembership, ...]
    findings: tuple[OrganisationReconciliationFinding, ...]

    def __post_init__(self) -> None:
        if self.checkpoint.status is not ReconciliationStatus.COMPLETED:
            raise ValueError("an atomic reconciliation plan requires a completed checkpoint")
        if self.checkpoint.completed_at != self.effective_at:
            raise ValueError("checkpoint completion must match the plan effective time")
        if any(unit.unit_id != revision.unit_id for unit, revision in self.units):
            raise ValueError("unit and revision identities must match")
