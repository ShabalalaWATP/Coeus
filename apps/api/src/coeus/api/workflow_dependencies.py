"""Focused dependencies for cross-service workflow orchestration."""

from fastapi import Request

from coeus.api.dependencies import (
    get_jioc_routing_agent_service,
    get_rfi_search_service,
    get_search_admission,
    get_similar_request_service,
    get_ticket_services,
)
from coeus.services.active_work_discovery import ActiveWorkDiscoveryService
from coeus.services.jioc_intervention import JiocInterventionService
from coeus.services.request_submission import RequestSubmissionService
from coeus.services.tasking_consent import TaskingConsentService


def get_active_work_discovery_service(request: Request) -> ActiveWorkDiscoveryService:
    return ActiveWorkDiscoveryService(
        get_ticket_services(request),
        get_similar_request_service(request),
    )


def get_request_submission_service(request: Request) -> RequestSubmissionService:
    return RequestSubmissionService(
        get_ticket_services(request),
        get_rfi_search_service(request),
        get_active_work_discovery_service(request),
        get_search_admission(request),
        request.app.state.settings.automatic_request_discovery_enabled,
        request.app.state.settings.active_work_offers_enabled,
    )


def get_tasking_consent_service(request: Request) -> TaskingConsentService:
    return TaskingConsentService(
        request.app.state.ticket_lifecycle_service,
        get_jioc_routing_agent_service(request),
        request.app.state.settings.jioc_agent_routing_enabled,
    )


def get_jioc_intervention_service(request: Request) -> JiocInterventionService:
    return JiocInterventionService(get_ticket_services(request))
