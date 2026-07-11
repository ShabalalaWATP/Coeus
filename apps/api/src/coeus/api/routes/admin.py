from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from coeus.api.dependencies import (
    get_access_services,
    get_ai_model_service,
    get_csrf_validated_session,
    get_notification_service,
    get_registration_service,
    get_settings,
    require_permission,
)
from coeus.core.config import Settings
from coeus.core.permissions import Permission
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.registration import RegistrationRequest
from coeus.schemas.registration import (
    AiConnectionTestRequest,
    AiConnectionTestResponse,
    AiCustomModelRequest,
    AiModelApiKeyRequest,
    AiModelRefreshRequest,
    AiModelSelectRequest,
    AiModelStateResponse,
    AiProviderSelectRequest,
    AiProviderStateResponse,
    RegistrationDecisionRequest,
    RegistrationListResponse,
    RegistrationResponse,
)
from coeus.services.access import AccessServices
from coeus.services.ai_models import AiModelService, AiModelState
from coeus.services.ai_provider_admin import notify_admins_of_provider_change, test_connection
from coeus.services.notifications import NotificationService
from coeus.services.registration import RegistrationService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview")
async def admin_overview(
    authenticated: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.SYSTEM_CONFIGURE)),
    ],
) -> dict[str, str]:
    return {
        "status": "available",
        "userId": str(authenticated.user.user_id),
        "scope": "admin-overview",
    }


@router.get("/ai-model", response_model=AiModelStateResponse)
async def ai_model_state(
    authenticated: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.SYSTEM_CONFIGURE)),
    ],
    ai_models: Annotated[AiModelService, Depends(get_ai_model_service)],
) -> AiModelStateResponse:
    return _ai_model_response(ai_models.state())


@router.put("/ai-model", response_model=AiModelStateResponse)
async def select_ai_model(
    payload: AiModelSelectRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    permitted: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.SYSTEM_CONFIGURE)),
    ],
    ai_models: Annotated[AiModelService, Depends(get_ai_model_service)],
) -> AiModelStateResponse:
    return _ai_model_response(
        ai_models.select(
            str(authenticated.user.user_id),
            authenticated.user.username,
            payload.model,
            payload.provider,
        )
    )


@router.post("/ai-model/refresh", response_model=AiModelStateResponse)
async def refresh_ai_models(
    payload: AiModelRefreshRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    permitted: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.SYSTEM_CONFIGURE)),
    ],
    ai_models: Annotated[AiModelService, Depends(get_ai_model_service)],
) -> AiModelStateResponse:
    return _ai_model_response(
        ai_models.refresh_models(
            str(authenticated.user.user_id), authenticated.user.username, payload.provider
        )
    )


@router.post("/ai-model/custom-model", response_model=AiModelStateResponse)
async def add_custom_ai_model(
    payload: AiCustomModelRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    permitted: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.SYSTEM_CONFIGURE)),
    ],
    ai_models: Annotated[AiModelService, Depends(get_ai_model_service)],
) -> AiModelStateResponse:
    return _ai_model_response(
        ai_models.add_custom_model(
            str(authenticated.user.user_id),
            authenticated.user.username,
            payload.provider,
            payload.model,
        )
    )


@router.put("/ai-model/provider", response_model=AiModelStateResponse)
async def select_ai_provider(
    payload: AiProviderSelectRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    permitted: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.SYSTEM_CONFIGURE)),
    ],
    ai_models: Annotated[AiModelService, Depends(get_ai_model_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    notifications: Annotated[NotificationService, Depends(get_notification_service)],
    access: Annotated[AccessServices, Depends(get_access_services)],
) -> AiModelStateResponse:
    previous = ai_models.provider()
    state = ai_models.select_provider(
        str(authenticated.user.user_id), authenticated.user.username, payload.provider
    )
    if state.provider != previous:
        # The switch applies app-wide immediately, so every administrator is
        # told who changed it and to what, not just the one who clicked.
        notify_admins_of_provider_change(
            notifications,
            access.repository.list_users(),
            authenticated.user,
            settings,
            state.provider,
            state.active_model,
        )
    return _ai_model_response(state)


@router.post("/ai-model/test", response_model=AiConnectionTestResponse)
async def test_ai_connection(
    payload: AiConnectionTestRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    permitted: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.SYSTEM_CONFIGURE)),
    ],
    ai_models: Annotated[AiModelService, Depends(get_ai_model_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AiConnectionTestResponse:
    result = test_connection(settings, ai_models, payload.provider)
    return AiConnectionTestResponse(
        ok=result.ok, provider=result.provider, model=result.model, message=result.message
    )


@router.put("/ai-model/api-key", response_model=AiModelStateResponse)
async def configure_ai_api_key(
    payload: AiModelApiKeyRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    permitted: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.SYSTEM_CONFIGURE)),
    ],
    ai_models: Annotated[AiModelService, Depends(get_ai_model_service)],
) -> AiModelStateResponse:
    return _ai_model_response(
        ai_models.configure_api_key(
            str(authenticated.user.user_id),
            authenticated.user.username,
            payload.api_key,
            payload.provider,
        )
    )


def _ai_model_response(state: AiModelState) -> AiModelStateResponse:
    return AiModelStateResponse(
        provider=state.provider,
        active_model=state.active_model,
        available_models=list(state.available_models),
        api_key_configured=state.api_key_configured,
        embedding_provider=state.embedding_provider,
        embedded_product_count=state.embedded_product_count,
        changed_by=state.changed_by,
        changed_at=state.changed_at,
        providers=[
            AiProviderStateResponse(
                name=provider.name,
                label=provider.label,
                models=list(provider.models),
                active_model=provider.active_model,
                api_key_configured=provider.api_key_configured,
            )
            for provider in state.providers
        ],
    )


@router.get("/registrations", response_model=RegistrationListResponse)
def list_registrations(
    authenticated: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.USER_CREATE)),
    ],
    registration_service: Annotated[RegistrationService, Depends(get_registration_service)],
) -> RegistrationListResponse:
    return RegistrationListResponse(
        registrations=[
            _registration_response(registration)
            for registration in registration_service.list_pending(authenticated.user)
        ]
    )


@router.post("/registrations/{registration_id}/approve", response_model=RegistrationResponse)
def approve_registration(
    registration_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    registration_service: Annotated[RegistrationService, Depends(get_registration_service)],
) -> RegistrationResponse:
    return _registration_response(registration_service.approve(authenticated.user, registration_id))


@router.post("/registrations/{registration_id}/reject", response_model=RegistrationResponse)
def reject_registration(
    registration_id: UUID,
    payload: RegistrationDecisionRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    registration_service: Annotated[RegistrationService, Depends(get_registration_service)],
) -> RegistrationResponse:
    return _registration_response(
        registration_service.reject(authenticated.user, registration_id, payload.reason)
    )


def _registration_response(registration: RegistrationRequest) -> RegistrationResponse:
    return RegistrationResponse(
        registration_id=registration.registration_id,
        username=registration.username,
        display_name=registration.display_name,
        justification=registration.justification,
        status=registration.status.value,
        created_at=registration.created_at,
    )
