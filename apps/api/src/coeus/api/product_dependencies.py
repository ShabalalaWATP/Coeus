"""Dependencies for external-product workflow services."""

from fastapi import Request

from coeus.services.customer_outcomes import CustomerOutcomeService
from coeus.services.product_submissions import ProductSubmissionService
from coeus.services.workflow_draft_access import WorkflowDraftAccessService


def get_product_submission_service(request: Request) -> ProductSubmissionService:
    service = getattr(request.app.state, "product_submission_service", None)
    if not isinstance(service, ProductSubmissionService):
        raise RuntimeError("Product submission service is unavailable.")
    return service


def get_workflow_draft_access_service(request: Request) -> WorkflowDraftAccessService:
    service = getattr(request.app.state, "workflow_draft_access_service", None)
    if not isinstance(service, WorkflowDraftAccessService):
        raise RuntimeError("Workflow draft access service is unavailable.")
    return service


def get_customer_outcome_service(request: Request) -> CustomerOutcomeService:
    service = getattr(request.app.state, "customer_outcome_service", None)
    if not isinstance(service, CustomerOutcomeService):
        raise RuntimeError("Customer outcome service is unavailable.")
    return service
