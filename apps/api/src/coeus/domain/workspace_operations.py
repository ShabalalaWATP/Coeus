"""Privacy-minimised integrated team workspace projections."""

import json
from dataclasses import dataclass
from datetime import datetime, time
from enum import StrEnum
from hashlib import sha256
from uuid import UUID


class WorkspaceOperationsDenied(PermissionError):
    pass


class WorkspaceOperationsConflict(RuntimeError):
    pass


class WorkspaceScope(StrEnum):
    DIRECT = "direct"
    DESCENDANTS = "descendants"


class PlanningCadence(StrEnum):
    WEEKLY = "weekly"
    FORTNIGHTLY = "fortnightly"
    MONTHLY = "monthly"


@dataclass(frozen=True)
class WorkspaceMetric:
    key: str
    label: str
    value: int | None
    display: str
    scope: WorkspaceScope
    period: str
    suppressed: bool = False


@dataclass(frozen=True)
class WorkspaceOverview:
    unit_id: UUID
    scope: WorkspaceScope
    generated_at: datetime
    fresh_until: datetime
    metrics: tuple[WorkspaceMetric, ...]
    descendant_units: int
    suppressed: bool


@dataclass(frozen=True)
class WorkspacePerson:
    user_id: UUID
    membership_role: str
    assignment_eligible: bool
    time_zone: str | None
    weekly_minutes: int | None


@dataclass(frozen=True)
class WorkspacePersonView:
    user_id: UUID
    display_name: str
    membership_role: str
    assignment_eligible: bool
    working_pattern: str


@dataclass(frozen=True)
class CapabilityCoverage:
    capability_id: str
    required_proficiency: int
    verified_people: int | None
    display: str
    gap: bool | None
    suppressed: bool


@dataclass(frozen=True)
class WorkspacePolicy:
    unit_id: UUID
    wip_limit: int
    service_target_hours: int
    planning_cadence: PlanningCadence
    planning_weekday: int
    planning_local_time: time
    planning_duration_minutes: int
    version: int
    delivery_policy_version: int
    updated_at: datetime


@dataclass(frozen=True)
class WorkspaceSearchResult:
    result_type: str
    object_id: UUID
    unit_id: UUID
    label: str
    context: str


@dataclass(frozen=True)
class WorkspaceAnalytics:
    unit_id: UUID
    scope: WorkspaceScope
    generated_at: datetime
    metrics: tuple[WorkspaceMetric, ...]
    privacy_notice: str


@dataclass(frozen=True)
class WorkspaceExport:
    export_id: UUID
    actor_user_id: UUID
    unit_id: UUID
    include_descendants: bool
    state: str
    row_count: int
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class WorkspaceCommand:
    command_id: UUID
    idempotency_key: str
    actor_user_id: UUID
    operation: str
    payload: dict[str, object]

    @property
    def request_hash(self) -> str:
        encoded = json.dumps(self.payload, default=str, sort_keys=True, separators=(",", ":"))
        return sha256(f"{self.operation}:".encode() + encoded.encode()).hexdigest()
