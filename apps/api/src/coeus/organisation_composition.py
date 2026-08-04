"""Fail-closed composition boundary for organisation authority modes."""

from datetime import UTC, datetime
from typing import cast

from fastapi import FastAPI
from sqlalchemy import create_engine

from coeus.api.identity_composition import IdentityComponents
from coeus.core.config import Settings
from coeus.domain.organisation_reconciliation import PROJECTION_ACTOR_ID
from coeus.organisation_administration_composition import (
    build_organisation_administration,
)
from coeus.persistence.cutover_activation_postgres import PostgresCutoverActivationStore
from coeus.persistence.database_url import synchronous_database_url
from coeus.persistence.organisation_postgres import PostgresOrganisationRepository
from coeus.persistence.organisation_reconciliation_postgres import (
    PostgresOrganisationReconciliation,
)
from coeus.persistence.package_lifecycle_reconciliation import reconcile_due_package_lifecycle
from coeus.persistence.team_task_ownership_postgres import (
    PostgresTeamTaskOwnershipRepository,
)
from coeus.repositories.teams import TeamRepository
from coeus.services.cutover_activation import CutoverActivationService
from coeus.services.organisation_reconciliation import OrganisationReconciliationService
from coeus.services.store import StoreServices


def configure_organisation_shadow(
    app: FastAPI,
    settings: Settings,
    identity: IdentityComponents,
    teams: TeamRepository,
) -> None:
    """Reconcile legacy authority into PostgreSQL without using it for decisions."""
    app.state.organisation_repository = None
    app.state.organisation_reconciliation_result = None
    app.state.organisation_engine = None
    app.state.team_task_ownership_repository = None
    app.state.organisation_administration = None
    app.state.task_ownership_reconciliation_result = None
    app.state.package_lifecycle_reconciliation_result = None
    app.state.cutover_activation_service = None
    if settings.organisation_mode == "disabled":
        return
    if settings.organisation_mode not in {"shadow", "management", "active"}:
        raise ValueError("unsupported organisation authority mode")

    engine = create_engine(
        synchronous_database_url(settings.database_url),
        pool_pre_ping=True,
    )
    app.state.organisation_repository = PostgresOrganisationRepository(engine)
    app.state.team_task_ownership_repository = PostgresTeamTaskOwnershipRepository(engine)
    app.state.organisation_engine = engine
    if settings.organisation_mode in {"management", "active"}:
        cutover = CutoverActivationService(PostgresCutoverActivationStore(engine))
        if settings.organisation_mode == "active":
            cutover.assert_active_composition_eligible(
                settings.organisation_active_candidate_hash,
                settings.organisation_cutover_source_revision,
            )
        administration = build_organisation_administration(
            engine,
            settings,
            identity,
            teams,
            cast(StoreServices, getattr(app.state, "store_services", None)),
        )
        app.state.cutover_activation_service = cutover
        app.state.organisation_administration = administration
        app.state.organisation_repository = administration.repository
        return
    service = OrganisationReconciliationService(PostgresOrganisationReconciliation(engine))
    app.state.organisation_reconciliation_result = service.reconcile(
        teams=teams.list_teams(),
        users=identity.users.list_users(),
        actor_user_id=PROJECTION_ACTOR_ID,
        effective_at=datetime.now(UTC),
    )


def reconcile_historical_task_ownership(app: FastAPI, settings: Settings) -> None:
    if settings.organisation_mode != "management":
        return
    administration = app.state.organisation_administration
    if administration is None:
        raise RuntimeError("Organisation management composition is unavailable.")
    app.state.task_ownership_reconciliation_result = (
        administration.task_ownership_reconciliation.reconcile()
    )
    engine = getattr(app.state, "organisation_engine", None)
    if engine is not None:
        app.state.package_lifecycle_reconciliation_result = reconcile_due_package_lifecycle(engine)
