from collections.abc import Callable

import pytest
from fastapi import FastAPI, Request

from coeus.api.dependencies import (
    get_access_services,
    get_admin_analytics_service,
    get_admission_metrics,
    get_ai_model_service,
    get_analyst_assignment_service,
    get_analyst_workflow_service,
    get_asset_token_service,
    get_auth_service,
    get_csrf_validated_session,
    get_feedback_analytics_service,
    get_manager_approval_service,
    get_manager_queue_service,
    get_notification_service,
    get_object_storage,
    get_quality_control_service,
    get_readiness_checker,
    get_registration_service,
    get_request_id,
    get_rfi_search_service,
    get_routing_service,
    get_search_admission,
    get_settings,
    get_similar_request_service,
    get_store_services,
    get_team_availability_service,
    get_team_calendar_service,
    get_team_repository,
    get_team_workspace_service,
    get_ticket_collaborator_service,
    get_ticket_lifecycle_service,
    get_ticket_services,
    get_upload_admission,
    get_user_admin_service,
    get_voice_model_service,
    get_voice_session_service,
)
from coeus.api.product_dependencies import (
    get_customer_outcome_service,
    get_product_submission_service,
    get_workflow_draft_access_service,
)
from coeus.api.search_dependencies import (
    get_search_configuration_service,
    get_search_embedding_service,
    get_search_indexing_service,
)
from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.db.session import DatabaseReadinessChecker


def empty_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "app": FastAPI(),
        }
    )


def test_get_readiness_checker_uses_configured_database_url() -> None:
    checker = get_readiness_checker(
        Settings(environment="test", database_url="postgresql+asyncpg://example")
    )

    assert isinstance(checker, DatabaseReadinessChecker)
    assert checker.database_url == "postgresql+asyncpg://example"


def test_get_request_id_returns_unknown_when_state_has_no_request_id() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})

    assert get_request_id(request) == "unknown"


@pytest.mark.parametrize(
    "dependency",
    [
        get_product_submission_service,
        get_workflow_draft_access_service,
        get_customer_outcome_service,
    ],
)
def test_missing_product_workflow_dependencies_fail_closed(
    dependency: Callable[[Request], object],
) -> None:
    with pytest.raises(RuntimeError, match="unavailable"):
        dependency(empty_request())


@pytest.mark.parametrize(
    ("dependency", "error_code"),
    [
        (get_settings, "settings_not_configured"),
        (get_admission_metrics, "metrics_not_configured"),
        (get_admin_analytics_service, "admin_analytics_not_configured"),
        (get_auth_service, "auth_not_configured"),
        (get_ticket_collaborator_service, "collaborators_not_configured"),
        (get_ticket_lifecycle_service, "ticket_lifecycle_not_configured"),
        (get_user_admin_service, "user_admin_not_configured"),
        (get_ai_model_service, "ai_models_not_configured"),
        (get_voice_model_service, "voice_not_configured"),
        (get_voice_session_service, "voice_not_configured"),
        (get_manager_approval_service, "approval_not_configured"),
        (get_manager_queue_service, "manager_queue_not_configured"),
        (get_analyst_assignment_service, "assignment_not_configured"),
        (get_notification_service, "notifications_not_configured"),
        (get_registration_service, "registration_not_configured"),
        (get_access_services, "access_not_configured"),
        (get_ticket_services, "tickets_not_configured"),
        (get_store_services, "store_not_configured"),
        (get_object_storage, "object_storage_not_configured"),
        (get_upload_admission, "upload_admission_not_configured"),
        (get_search_admission, "search_admission_not_configured"),
        (get_asset_token_service, "asset_tokens_not_configured"),
        (get_rfi_search_service, "rfi_search_not_configured"),
        (get_routing_service, "routing_not_configured"),
        (get_similar_request_service, "similar_requests_not_configured"),
        (get_analyst_workflow_service, "analyst_not_configured"),
        (get_quality_control_service, "qc_not_configured"),
        (get_team_workspace_service, "teams_not_configured"),
        (get_team_availability_service, "teams_not_configured"),
        (get_team_calendar_service, "teams_not_configured"),
        (get_team_repository, "teams_not_configured"),
        (get_feedback_analytics_service, "feedback_analytics_not_configured"),
        (get_search_configuration_service, "search_not_configured"),
        (get_search_embedding_service, "search_not_configured"),
        (get_search_indexing_service, "search_not_configured"),
    ],
)
def test_missing_application_dependencies_fail_closed(
    dependency: Callable[[Request], object], error_code: str
) -> None:
    with pytest.raises(AppError) as error:
        dependency(empty_request())

    assert error.value.status_code == 500
    assert error.value.code == error_code


def test_csrf_dependency_rejects_a_misconfigured_header() -> None:
    settings = Settings(environment="test", csrf_header_name="X-Other-CSRF")

    with pytest.raises(AppError, match="CSRF header is misconfigured"):
        get_csrf_validated_session(settings, object(), object())  # type: ignore[arg-type]
