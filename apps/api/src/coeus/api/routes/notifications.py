from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from coeus.api.dependencies import (
    get_csrf_validated_session,
    get_current_session,
    get_notification_service,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.notifications import NotificationRecord
from coeus.schemas.notifications import NotificationListResponse, NotificationResponse
from coeus.services.notifications import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    notifications: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationListResponse:
    records = notifications.list_for_user(authenticated.user)
    return NotificationListResponse(
        notifications=[_to_response(record) for record in records],
        unread=sum(1 for record in records if not record.read),
    )


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    notifications: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationResponse:
    return _to_response(notifications.mark_read(authenticated.user, notification_id))


def _to_response(record: NotificationRecord) -> NotificationResponse:
    return NotificationResponse(
        notification_id=record.notification_id,
        kind=record.kind,
        title=record.title,
        body=record.body,
        link_path=record.link_path,
        read=record.read,
        created_at=record.created_at,
    )
