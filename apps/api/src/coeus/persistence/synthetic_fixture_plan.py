"""Internal immutable plan assembled from a synthetic fixture preview."""

from dataclasses import dataclass

from coeus.domain.organisation import ManagementAction
from coeus.domain.synthetic_organisation_fixture import SyntheticFixturePreview
from coeus.repositories.synthetic_calendar_manifest import SyntheticCalendarEventSpec
from coeus.repositories.synthetic_capability_manifest import (
    SyntheticAnalystCompetencySpec,
    SyntheticTeamCapabilitySpec,
)
from coeus.repositories.synthetic_capacity_manifest import SyntheticCapacityReservationSpec
from coeus.repositories.synthetic_grant_manifest import (
    SyntheticManagementGrantSpec,
    SyntheticServiceGrantSpec,
)
from coeus.repositories.synthetic_organisation_manifest import (
    SyntheticPostingSpec,
    SyntheticUnitSpec,
    SyntheticWorkingPatternSpec,
)
from coeus.repositories.synthetic_task_manifest import SyntheticTaskSpec


@dataclass(frozen=True)
class SyntheticFixturePlan:
    preview: SyntheticFixturePreview
    units: tuple[SyntheticUnitSpec, ...]
    profiles: tuple[SyntheticUnitSpec, ...]
    memberships: tuple[SyntheticPostingSpec, ...]
    patterns: tuple[SyntheticWorkingPatternSpec, ...]
    grants: tuple[ManagementAction, ...]
    team_capabilities: tuple[SyntheticTeamCapabilitySpec, ...]
    competencies: tuple[SyntheticAnalystCompetencySpec, ...]
    calendar_events: tuple[SyntheticCalendarEventSpec, ...]
    management_grants: tuple[SyntheticManagementGrantSpec, ...]
    service_grants: tuple[SyntheticServiceGrantSpec, ...]
    tasks: tuple[SyntheticTaskSpec, ...]
    task_ownership: tuple[SyntheticTaskSpec, ...]
    work_packages: tuple[tuple[SyntheticTaskSpec, int], ...]
    capacity_reservations: tuple[SyntheticCapacityReservationSpec, ...]
    create_bootstrap_marker: bool
