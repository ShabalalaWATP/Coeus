from collections.abc import Callable

import pytest
from fastapi import FastAPI, Request

from coeus.api.dependencies import (
    get_access_services,
    get_ai_model_service,
    get_analyst_workflow_service,
    get_asset_token_service,
    get_auth_service,
    get_csrf_validated_session,
    get_feedback_analytics_service,
    get_notification_service,
    get_object_storage,
    get_product_release_service,
    get_quality_control_service,
    get_readiness_checker,
    get_registration_service,
    get_request_id,
    get_rfi_search_service,
    get_routing_service,
    get_settings,
    get_similar_request_service,
    get_store_services,
    get_ticket_collaborator_service,
    get_ticket_lifecycle_service,
    get_ticket_services,
    get_user_admin_service,
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
    ("dependency", "error_code"),
    [
        (get_settings, "settings_not_configured"),
        (get_auth_service, "auth_not_configured"),
        (get_ticket_collaborator_service, "collaborators_not_configured"),
        (get_ticket_lifecycle_service, "ticket_lifecycle_not_configured"),
        (get_user_admin_service, "user_admin_not_configured"),
        (get_ai_model_service, "ai_models_not_configured"),
        (get_product_release_service, "release_not_configured"),
        (get_notification_service, "notifications_not_configured"),
        (get_registration_service, "registration_not_configured"),
        (get_access_services, "access_not_configured"),
        (get_ticket_services, "tickets_not_configured"),
        (get_store_services, "store_not_configured"),
        (get_object_storage, "object_storage_not_configured"),
        (get_asset_token_service, "asset_tokens_not_configured"),
        (get_rfi_search_service, "rfi_search_not_configured"),
        (get_routing_service, "routing_not_configured"),
        (get_similar_request_service, "similar_requests_not_configured"),
        (get_analyst_workflow_service, "analyst_not_configured"),
        (get_quality_control_service, "qc_not_configured"),
        (get_feedback_analytics_service, "feedback_analytics_not_configured"),
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
