"""Actor-scoped organisation workspace projections."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from coeus.domain.organisation import OrganisationUnit


class WorkspaceRelationship(StrEnum):
    HOME = "home"
    MANAGED = "managed"


@dataclass(frozen=True)
class OrganisationWorkspace:
    unit: OrganisationUnit
    relationship: WorkspaceRelationship
    managed: bool
    include_descendants: bool
    can_view_availability: bool
    can_view_detail: bool
    can_view_tasks: bool
    planning_grant_id: UUID | None
    configuration_grant_id: UUID | None = None
    configuration_grant_version: int | None = None
    calendar_management_grant_id: UUID | None = None
    can_view_people: bool = False
    can_view_capabilities: bool = False
    can_configure: bool = False
    export_grant_id: UUID | None = None
    export_grant_version: int | None = None


@dataclass(frozen=True)
class OrganisationWorkspacePage:
    workspaces: tuple[OrganisationWorkspace, ...]
    as_of: datetime
    truncated: bool


class OrganisationWorkspaceIntegrityError(RuntimeError):
    """Raised when relational workspace invariants are not safe to project."""
