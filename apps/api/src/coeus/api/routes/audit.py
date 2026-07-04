from typing import Annotated

from fastapi import APIRouter, Depends

from coeus.api.dependencies import get_auth_service, require_permission
from coeus.core.permissions import Permission
from coeus.domain.auth import AuthenticatedSession
from coeus.schemas.auth import AuditEventResponse, AuditLogResponse
from coeus.services.auth import AuthService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=AuditLogResponse)
async def list_audit_events(
    _authenticated: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.AUDIT_READ)),
    ],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuditLogResponse:
    return AuditLogResponse(
        events=[
            AuditEventResponse(
                event_id=event.event_id,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                actor_user_id=event.actor_user_id,
                metadata=dict(event.metadata),
            )
            for event in auth_service.audit_log.list_events()
        ]
    )
