from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from coeus.api.dependencies import (
    get_ai_model_service,
    get_csrf_validated_session,
    get_registration_service,
    require_permission,
)
from coeus.core.permissions import Permission
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.registration import RegistrationRequest
from coeus.schemas.registration import (
    AiModelApiKeyRequest,
    AiModelSelectRequest,
    AiModelStateResponse,
    RegistrationDecisionRequest,
    RegistrationListResponse,
    RegistrationResponse,
)
from coeus.services.ai_models import AiModelService, AiModelState
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
            str(authenticated.user.user_id), authenticated.user.username, payload.model
        )
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
        )
    )


def _ai_model_response(state: AiModelState) -> AiModelStateResponse:
    return AiModelStateResponse(
        provider=state.provider,
        active_model=state.active_model,
        available_models=list(state.available_models),
        api_key_configured=state.api_key_configured,
        changed_by=state.changed_by,
        changed_at=state.changed_at,
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
