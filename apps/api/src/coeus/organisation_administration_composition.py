"""Composition for the management-only organisation command boundary."""

from dataclasses import dataclass

from sqlalchemy.engine import Engine

from coeus.api.identity_composition import IdentityComponents
from coeus.core.config import Settings
from coeus.persistence.assignment_recommendations_postgres import (
    PostgresAssignmentRecommendationStore,
)
from coeus.persistence.calendar_import_postgres import PostgresCalendarImportStore
from coeus.persistence.cutover_readiness_postgres import PostgresCutoverReadinessStore
from coeus.persistence.my_work_postgres import PostgresMyWorkStore
from coeus.persistence.organisation_authority_postgres import (
    PostgresOrganisationGrantCommandStore,
)
from coeus.persistence.organisation_bootstrap_postgres import (
    PostgresOrganisationBootstrapStore,
)
from coeus.persistence.organisation_deactivation_postgres import (
    PostgresOrganisationDeactivationStore,
)
from coeus.persistence.organisation_lifecycle_postgres import (
    PostgresOrganisationMutationStore,
)
from coeus.persistence.organisation_membership_postgres import (
    PostgresOrganisationMembershipStore,
)
from coeus.persistence.organisation_merge_postgres import PostgresOrganisationMergeStore
from coeus.persistence.organisation_postgres import PostgresOrganisationRepository
from coeus.persistence.organisation_reparent_postgres import PostgresOrganisationReparentStore
from coeus.persistence.organisation_split_postgres import PostgresOrganisationSplitStore
from coeus.persistence.organisation_transfer_postgres import PostgresOrganisationTransferStore
from coeus.persistence.organisation_workspace_postgres import PostgresOrganisationWorkspaceStore
from coeus.persistence.package_predecessor_cancellation_postgres import (
    PostgresPredecessorCancellationStore,
)
from coeus.persistence.synthetic_organisation_fixture_postgres import (
    PostgresSyntheticOrganisationFixtureStore,
)
from coeus.persistence.task_ownership_reconciliation_postgres import (
    PostgresTaskOwnershipReconciliationStore,
)
from coeus.persistence.team_capacity_forecast_postgres import PostgresTeamCapacityForecastStore
from coeus.persistence.team_task_board_postgres import PostgresTeamTaskBoardStore
from coeus.persistence.work_package_contributors_postgres import (
    PostgresWorkPackageContributorStore,
)
from coeus.persistence.work_package_dependencies_postgres import (
    PostgresWorkPackageDependencyStore,
)
from coeus.persistence.work_package_handovers_postgres import PostgresWorkPackageHandoverStore
from coeus.persistence.work_package_planning_postgres import PostgresWorkPackagePlanningStore
from coeus.persistence.workflow_leg_transfers_postgres import PostgresWorkflowLegTransferStore
from coeus.persistence.workforce_calendar_postgres import PostgresWorkforceCalendarStore
from coeus.persistence.workspace_operations_postgres import PostgresWorkspaceOperationsStore
from coeus.persistence.workspace_productivity_postgres import PostgresWorkspaceProductivityStore
from coeus.repositories.teams import TeamRepository
from coeus.services.calendar_import import CalendarImportService
from coeus.services.cutover_readiness import CutoverReadinessService
from coeus.services.my_work import MyWorkService
from coeus.services.organisation_authority import OrganisationGrantService
from coeus.services.organisation_bootstrap import OrganisationBootstrapService
from coeus.services.organisation_deactivation import OrganisationDeactivationService
from coeus.services.organisation_lifecycle import OrganisationLifecycleService
from coeus.services.organisation_membership import OrganisationMembershipService
from coeus.services.organisation_merge import OrganisationMergeService
from coeus.services.organisation_reparent import OrganisationReparentService
from coeus.services.organisation_split import OrganisationSplitService
from coeus.services.organisation_transfer import OrganisationTransferService
from coeus.services.organisation_workspace import OrganisationWorkspaceService
from coeus.services.package_predecessor_cancellation import PredecessorCancellationService
from coeus.services.store import StoreServices
from coeus.services.synthetic_organisation_fixture import (
    SyntheticOrganisationFixtureService,
)
from coeus.services.task_ownership_reconciliation import TaskOwnershipReconciliationService
from coeus.services.team_capacity_forecast import TeamCapacityForecastService
from coeus.services.team_task_board import TeamTaskBoardService
from coeus.services.work_package_contributors import WorkPackageContributorService
from coeus.services.work_package_dependencies import WorkPackageDependencyService
from coeus.services.work_package_handovers import WorkPackageHandoverService
from coeus.services.work_package_planning import WorkPackagePlanningService
from coeus.services.workflow_leg_transfers import WorkflowLegTransferService
from coeus.services.workforce_calendar import WorkforceCalendarService
from coeus.services.workspace_operations import WorkspaceOperationsService
from coeus.services.workspace_productivity import WorkspaceProductivityService


@dataclass(frozen=True)
class OrganisationAdministration:
    repository: PostgresOrganisationRepository
    bootstrap: OrganisationBootstrapService
    grants: OrganisationGrantService
    lifecycle: OrganisationLifecycleService
    reparent: OrganisationReparentService
    memberships: OrganisationMembershipService
    transfers: OrganisationTransferService
    deactivation: OrganisationDeactivationService
    merge: OrganisationMergeService
    split: OrganisationSplitService
    calendar: WorkforceCalendarService
    workspace: OrganisationWorkspaceService
    task_board: TeamTaskBoardService
    work_package_planning: WorkPackagePlanningService
    work_package_contributors: WorkPackageContributorService
    work_package_dependencies: WorkPackageDependencyService
    predecessor_cancellation: PredecessorCancellationService
    work_package_handovers: WorkPackageHandoverService
    workflow_leg_transfers: WorkflowLegTransferService
    my_work: MyWorkService
    team_capacity_forecast: TeamCapacityForecastService
    task_ownership_reconciliation: TaskOwnershipReconciliationService
    synthetic_fixture: SyntheticOrganisationFixtureService
    cutover_readiness: CutoverReadinessService
    calendar_import: CalendarImportService
    assignment_recommendations: PostgresAssignmentRecommendationStore
    workspace_productivity: WorkspaceProductivityService
    workspace_operations: WorkspaceOperationsService


def build_organisation_administration(
    engine: Engine,
    settings: Settings,
    identity: IdentityComponents,
    teams: TeamRepository,
    store_services: StoreServices,
) -> OrganisationAdministration:
    repository = PostgresOrganisationRepository(engine)
    return OrganisationAdministration(
        repository,
        OrganisationBootstrapService(
            PostgresOrganisationBootstrapStore(engine), settings.organisation_setup_nonce
        ),
        OrganisationGrantService(repository, PostgresOrganisationGrantCommandStore(engine)),
        OrganisationLifecycleService(repository, PostgresOrganisationMutationStore(engine)),
        OrganisationReparentService(repository, PostgresOrganisationReparentStore(engine)),
        OrganisationMembershipService(
            repository, identity.access, PostgresOrganisationMembershipStore(engine)
        ),
        OrganisationTransferService(
            repository, identity.access, PostgresOrganisationTransferStore(engine)
        ),
        OrganisationDeactivationService(repository, PostgresOrganisationDeactivationStore(engine)),
        OrganisationMergeService(repository, PostgresOrganisationMergeStore(engine)),
        OrganisationSplitService(repository, PostgresOrganisationSplitStore(engine)),
        WorkforceCalendarService(
            repository, identity.access, PostgresWorkforceCalendarStore(engine)
        ),
        OrganisationWorkspaceService(PostgresOrganisationWorkspaceStore(engine)),
        TeamTaskBoardService(PostgresTeamTaskBoardStore(engine)),
        WorkPackagePlanningService(PostgresWorkPackagePlanningStore(engine)),
        WorkPackageContributorService(PostgresWorkPackageContributorStore(engine)),
        WorkPackageDependencyService(PostgresWorkPackageDependencyStore(engine)),
        PredecessorCancellationService(PostgresPredecessorCancellationStore(engine)),
        WorkPackageHandoverService(PostgresWorkPackageHandoverStore(engine)),
        WorkflowLegTransferService(PostgresWorkflowLegTransferStore(engine)),
        MyWorkService(PostgresMyWorkStore(engine)),
        TeamCapacityForecastService(PostgresTeamCapacityForecastStore(engine)),
        TaskOwnershipReconciliationService(PostgresTaskOwnershipReconciliationStore(engine)),
        SyntheticOrganisationFixtureService(
            PostgresSyntheticOrganisationFixtureStore(engine),
            identity.users,
            enabled=(
                settings.environment in {"local", "test"}
                and settings.organisation_demo_seed_enabled
            ),
        ),
        CutoverReadinessService(PostgresCutoverReadinessStore(engine)),
        CalendarImportService(teams, PostgresCalendarImportStore(engine)),
        PostgresAssignmentRecommendationStore(engine),
        WorkspaceProductivityService(
            PostgresWorkspaceProductivityStore(engine),
            store_services.details,
            store_services.projects,
        ),
        WorkspaceOperationsService(
            PostgresWorkspaceOperationsStore(engine),
            identity.access,
            store_services.details,
            store_services.projects,
            store_services.search,
        ),
    )
