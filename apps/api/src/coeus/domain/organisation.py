"""Validated records for the disabled-by-default organisation foundation."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from itertools import pairwise
from uuid import UUID

from coeus.domain.organisation_validation import (
    aware as _aware,
)
from coeus.domain.organisation_validation import (
    interval as _interval,
)
from coeus.domain.organisation_validation import (
    optional_text as _optional_text,
)
from coeus.domain.organisation_validation import (
    text_value as _text,
)

MAX_ORGANISATION_DEPTH = 12


class OrganisationCategory(StrEnum):
    COMMAND = "command"
    BRANCH = "branch"
    CUSTOMER_TEAM = "customer_team"
    DELIVERY_TEAM = "delivery_team"
    GOVERNANCE_TEAM = "governance_team"
    OTHER = "other"


class DeliveryRoute(StrEnum):
    RFA = "rfa"
    CM = "cm"
    JIOC = "jioc"
    QC = "qc"


class MembershipRole(StrEnum):
    MEMBER = "member"
    MANAGER = "manager"
    DEPUTY = "deputy"
    COORDINATOR = "coordinator"


class MembershipState(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ENDED = "ended"
    CANCELLED = "cancelled"


class ManagementAction(StrEnum):
    ORGANISATION_VIEW = "organisation:view"
    ORGANISATION_VIEW_AGGREGATE = "organisation:view_aggregate"
    ROSTER_VIEW = "roster:view"
    ROSTER_MANAGE = "roster:manage"
    ROSTER_TRANSFER = "roster:transfer"
    CALENDAR_VIEW_AVAILABILITY = "calendar:view_availability"
    CALENDAR_VIEW_DETAIL = "calendar:view_detail"
    CALENDAR_MANAGE = "calendar:manage"
    TASK_VIEW = "task:view"
    TASK_ASSIGN = "task:assign"
    TASK_APPROVE = "task:approve"
    TASK_TRANSFER = "task:transfer"
    RECOMMENDATION_VIEW = "recommendation:view"
    RECOMMENDATION_OVERRIDE = "recommendation:override"
    WORKSPACE_VIEW = "workspace:view"
    WORKSPACE_CONFIGURE = "workspace:configure"
    WORKSPACE_EXPORT = "workspace:export"
    WORK_UPDATE_VIEW = "work_update:view"
    CAPABILITY_MANAGE = "capability:manage"
    ORGANISATION_CREATE = "organisation:create"
    ORGANISATION_EDIT = "organisation:edit"
    ORGANISATION_REPARENT = "organisation:reparent"
    ORGANISATION_RESTRUCTURE = "organisation:restructure"
    GRANT_MANAGE = "grant:manage"
    GRANT_DELEGATE = "grant:delegate"


class ReconciliationStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FindingSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


@dataclass(frozen=True)
class OrganisationUnit:
    unit_id: UUID
    name: str
    short_name: str
    category: OrganisationCategory
    parent_unit_id: UUID | None
    valid_from: datetime
    valid_until: datetime | None = None
    time_zone: str = "Europe/London"
    description: str = ""
    is_active: bool = True
    version: int = 1
    provenance: str = "manual"

    def __post_init__(self) -> None:
        _text(self.name, "name", 120)
        _text(self.short_name, "short_name", 32)
        _text(self.time_zone, "time_zone", 64)
        _optional_text(self.description, "description", 1_000)
        _text(self.provenance, "provenance", 120)
        _interval(self.valid_from, self.valid_until)
        if self.parent_unit_id == self.unit_id:
            raise ValueError("an organisation unit cannot parent itself")
        if self.version < 1:
            raise ValueError("version must be positive")


@dataclass(frozen=True)
class OrganisationClosureRow:
    ancestor_unit_id: UUID
    descendant_unit_id: UUID
    depth: int

    def __post_init__(self) -> None:
        if not 0 <= self.depth <= MAX_ORGANISATION_DEPTH:
            raise ValueError("closure depth must be between 0 and 12")
        is_self = self.ancestor_unit_id == self.descendant_unit_id
        if is_self != (self.depth == 0):
            raise ValueError("only a depth-zero closure row may reference itself")


@dataclass(frozen=True)
class OrganisationTopologyRevision:
    revision_id: UUID
    unit_id: UUID
    parent_unit_id: UUID | None
    path: tuple[UUID, ...]
    valid_from: datetime
    change_command_id: UUID
    changed_by_user_id: UUID
    valid_until: datetime | None = None

    def __post_init__(self) -> None:
        _interval(self.valid_from, self.valid_until)
        if not self.path or self.path[-1] != self.unit_id:
            raise ValueError("topology path must end with its unit")
        if len(self.path) != len(set(self.path)):
            raise ValueError("topology path cannot contain a cycle")
        if len(self.path) - 1 > MAX_ORGANISATION_DEPTH:
            raise ValueError("topology path exceeds maximum depth")
        expected_parent = self.path[-2] if len(self.path) > 1 else None
        if self.parent_unit_id != expected_parent:
            raise ValueError("topology parent must match the recorded path")


@dataclass(frozen=True)
class TeamMembership:
    membership_id: UUID
    user_id: UUID
    unit_id: UUID
    role: MembershipRole
    state: MembershipState
    assignment_eligible: bool
    valid_from: datetime
    created_by_user_id: UUID
    reason: str
    provenance: str
    valid_until: datetime | None = None
    version: int = 1

    def __post_init__(self) -> None:
        _interval(self.valid_from, self.valid_until)
        _text(self.reason, "reason", 500)
        _text(self.provenance, "provenance", 120)
        if self.state is MembershipState.ENDED and self.valid_until is None:
            raise ValueError("an ended membership requires valid_until")
        if self.state is not MembershipState.ACTIVE and self.assignment_eligible:
            raise ValueError("only an active membership can be assignment eligible")
        if self.version < 1:
            raise ValueError("version must be positive")


@dataclass(frozen=True)
class OrganisationManagementGrant:
    grant_id: UUID
    manager_user_id: UUID
    root_unit_id: UUID
    action: ManagementAction
    include_descendants: bool
    valid_from: datetime
    created_by_user_id: UUID
    reason: str
    valid_until: datetime | None = None
    revoked_at: datetime | None = None
    source_grant_id: UUID | None = None
    delegation_depth: int = 0
    version: int = 1
    revoked_by_user_id: UUID | None = None
    revocation_reason: str = ""

    def __post_init__(self) -> None:
        _interval(self.valid_from, self.valid_until)
        _aware(self.revoked_at, "revoked_at")
        _text(self.reason, "reason", 500)
        if not 0 <= self.delegation_depth <= 2:
            raise ValueError("delegation depth must be between zero and two")
        if self.source_grant_id is None and self.delegation_depth != 0:
            raise ValueError("a delegated grant requires its source grant")
        if self.source_grant_id == self.grant_id:
            raise ValueError("a grant cannot delegate from itself")
        if self.version < 1:
            raise ValueError("version must be positive")
        _optional_text(self.revocation_reason, "revocation_reason", 500)
        if self.revoked_at is not None and self.revoked_at < self.valid_from:
            raise ValueError("revoked_at cannot precede valid_from")
        if (
            self.revoked_at is not None
            and self.valid_until is not None
            and self.revoked_at > self.valid_until
        ):
            raise ValueError("revoked_at cannot follow valid_until")


@dataclass(frozen=True)
class TeamDeliveryProfile:
    profile_id: UUID
    unit_id: UUID
    route: DeliveryRoute
    wip_limit: int
    weekly_hours: float
    policy_version: int = 1
    is_active: bool = True
    provenance: str = "manual"

    def __post_init__(self) -> None:
        if self.wip_limit < 1:
            raise ValueError("wip_limit must be positive")
        if not 0 < self.weekly_hours <= 168:
            raise ValueError("weekly_hours must be between zero and 168")
        if self.policy_version < 1:
            raise ValueError("policy_version must be positive")
        _text(self.provenance, "provenance", 120)


@dataclass(frozen=True)
class TeamCapabilityCoverage:
    coverage_id: UUID
    profile_id: UUID
    capability_id: str
    proficiency: int
    valid_from: datetime
    approved_by_user_id: UUID
    policy_version: int = 1
    valid_until: datetime | None = None

    def __post_init__(self) -> None:
        _text(self.capability_id, "capability_id", 120)
        _interval(self.valid_from, self.valid_until)
        if not 1 <= self.proficiency <= 5:
            raise ValueError("proficiency must be between one and five")
        if self.policy_version < 1:
            raise ValueError("policy_version must be positive")


@dataclass(frozen=True)
class EffectiveAuthorityEpoch:
    principal_id: UUID
    scope_unit_id: UUID
    epoch: int
    advanced_at: datetime

    def __post_init__(self) -> None:
        _aware(self.advanced_at, "advanced_at")
        if self.epoch < 1:
            raise ValueError("authority epoch must be positive")


@dataclass(frozen=True)
class OrganisationReconciliationCheckpoint:
    checkpoint_id: UUID
    source_namespace: str
    source_digest: str
    status: ReconciliationStatus
    started_at: datetime
    cursor: dict[str, object]
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        _text(self.source_namespace, "source_namespace", 120)
        _text(self.source_digest, "source_digest", 128)
        _aware(self.started_at, "started_at")
        _aware(self.completed_at, "completed_at")
        if self.status is ReconciliationStatus.RUNNING and self.completed_at is not None:
            raise ValueError("a running checkpoint cannot be completed")
        if self.status is not ReconciliationStatus.RUNNING and self.completed_at is None:
            raise ValueError("a terminal checkpoint requires completed_at")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")


@dataclass(frozen=True)
class OrganisationReconciliationFinding:
    finding_id: UUID
    checkpoint_id: UUID
    finding_code: str
    severity: FindingSeverity
    source_identifier: str
    details: dict[str, object]
    created_at: datetime
    resolved_at: datetime | None = None
    disposition: str = ""

    def __post_init__(self) -> None:
        _text(self.finding_code, "finding_code", 120)
        _text(self.source_identifier, "source_identifier", 240)
        _optional_text(self.disposition, "disposition", 500)
        _aware(self.created_at, "created_at")
        _aware(self.resolved_at, "resolved_at")
        if self.resolved_at is not None and self.resolved_at < self.created_at:
            raise ValueError("resolved_at cannot precede created_at")


def validate_membership_history(memberships: tuple[TeamMembership, ...]) -> None:
    """Reject overlapping non-cancelled half-open membership intervals."""
    user_ids = {item.user_id for item in memberships}
    for user_id in user_ids:
        active = sorted(
            (
                item
                for item in memberships
                if item.user_id == user_id and item.state is not MembershipState.CANCELLED
            ),
            key=lambda item: item.valid_from,
        )
        for earlier, later in pairwise(active):
            if earlier.valid_until is None or later.valid_from < earlier.valid_until:
                raise ValueError("non-cancelled memberships cannot overlap")
