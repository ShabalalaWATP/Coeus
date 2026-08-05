"""Application ports for the shadow organisation foundation."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from coeus.domain.organisation import (
    EffectiveAuthorityEpoch,
    OrganisationManagementGrant,
    OrganisationReconciliationCheckpoint,
    OrganisationReconciliationFinding,
    OrganisationTopologyRevision,
    OrganisationUnit,
    TeamCapabilityCoverage,
    TeamDeliveryProfile,
    TeamMembership,
)


class OrganisationReader(Protocol):
    def get_unit(self, unit_id: UUID) -> OrganisationUnit | None: ...

    def list_roots(self, *, limit: int = 100) -> tuple[OrganisationUnit, ...]: ...

    def list_children(self, unit_id: UUID, *, limit: int = 100) -> tuple[OrganisationUnit, ...]: ...

    def list_ancestors(
        self, unit_id: UUID, *, maximum_depth: int = 12
    ) -> tuple[OrganisationUnit, ...]: ...

    def list_descendants(
        self, unit_id: UUID, *, maximum_depth: int = 12, limit: int = 1_000
    ) -> tuple[OrganisationUnit, ...]: ...

    def list_memberships(self, user_id: UUID) -> tuple[TeamMembership, ...]: ...

    def list_unit_memberships(
        self, unit_id: UUID, *, include_inactive: bool = False, limit: int = 200
    ) -> tuple[TeamMembership, ...]: ...

    def effective_membership(
        self, user_id: UUID, effective_at: datetime
    ) -> TeamMembership | None: ...

    def effective_grants(
        self, manager_user_id: UUID, effective_at: datetime
    ) -> tuple[OrganisationManagementGrant, ...]: ...

    def get_management_grant(self, grant_id: UUID) -> OrganisationManagementGrant | None: ...

    def list_management_grants(
        self,
        *,
        root_unit_id: UUID | None = None,
        manager_user_id: UUID | None = None,
        include_inactive: bool = False,
        limit: int = 100,
    ) -> tuple[OrganisationManagementGrant, ...]: ...

    def unit_is_within(self, root_unit_id: UUID, target_unit_id: UUID) -> bool: ...


class OrganisationShadowWriter(Protocol):
    """Idempotent, transaction-bounded primitives for shadow reconciliation."""

    def upsert_unit(
        self, unit: OrganisationUnit, revision: OrganisationTopologyRevision
    ) -> None: ...

    def upsert_membership(self, membership: TeamMembership) -> None: ...

    def upsert_management_grant(self, grant: OrganisationManagementGrant) -> None: ...

    def upsert_delivery_profile(self, profile: TeamDeliveryProfile) -> None: ...

    def upsert_capability_coverage(self, coverage: TeamCapabilityCoverage) -> None: ...

    def upsert_authority_epoch(self, epoch: EffectiveAuthorityEpoch) -> None: ...

    def upsert_checkpoint(self, checkpoint: OrganisationReconciliationCheckpoint) -> None: ...

    def upsert_finding(self, finding: OrganisationReconciliationFinding) -> None: ...


class OrganisationRepository(OrganisationReader, OrganisationShadowWriter, Protocol):
    pass
