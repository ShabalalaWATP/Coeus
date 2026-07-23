"""Application composition for external-product workflow services."""

from fastapi import FastAPI

from coeus.core.config import Settings
from coeus.repositories.access import AccessRepository
from coeus.repositories.teams import TeamRepository
from coeus.services.customer_outcomes import CustomerOutcomeService
from coeus.services.product_submissions import ProductSubmissionService
from coeus.services.workflow_draft_access import (
    WorkflowDraftAccessPolicy,
    WorkflowDraftAccessService,
)


def configure_product_workflow(
    app: FastAPI,
    settings: Settings,
    access: AccessRepository,
    teams: TeamRepository,
) -> WorkflowDraftAccessPolicy:
    policy = WorkflowDraftAccessPolicy(access, teams)
    app.state.customer_outcome_service = CustomerOutcomeService(app.state.ticket_services)
    app.state.product_submission_service = ProductSubmissionService(
        app.state.ticket_services,
        app.state.analyst_workflow_service,
        access,
        app.state.object_storage,
        settings,
        app.state.state_store,
    )
    app.state.workflow_draft_access_service = WorkflowDraftAccessService(
        app.state.ticket_services,
        policy,
        app.state.object_storage,
    )
    return policy
