"""Management-only preview and apply routes for legacy calendars."""

from typing import Annotated

from fastapi import APIRouter, Depends

from coeus.api.calendar_import_contracts import (
    call_calendar_import,
    preview_response,
    result_response,
)
from coeus.api.organisation_dependencies import (
    get_calendar_import,
    get_organisation_admin_csrf_session,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.calendar_import import CalendarImportCommand
from coeus.schemas.calendar_import import (
    CalendarImportCommandRequest,
    CalendarImportPreviewResponse,
    CalendarImportResultResponse,
)
from coeus.services.calendar_import import CalendarImportService

router = APIRouter(prefix="/admin/organisation/calendar-import", tags=["calendar import"])
AdminSessionDep = Annotated[AuthenticatedSession, Depends(get_organisation_admin_csrf_session)]
ImportDep = Annotated[CalendarImportService, Depends(get_calendar_import)]


@router.post("/preview", response_model=CalendarImportPreviewResponse)
async def preview_calendar_import(
    authenticated: AdminSessionDep,
    service: ImportDep,
) -> CalendarImportPreviewResponse:
    preview = call_calendar_import(lambda: service.preview(authenticated.user.user_id))
    return preview_response(preview)


@router.post("/commands", response_model=CalendarImportResultResponse)
async def apply_calendar_import(
    payload: CalendarImportCommandRequest,
    authenticated: AdminSessionDep,
    service: ImportDep,
) -> CalendarImportResultResponse:
    command = call_calendar_import(
        lambda: CalendarImportCommand(
            payload.command_id,
            payload.idempotency_key,
            authenticated.user.user_id,
            payload.preview_hash,
        )
    )
    return result_response(call_calendar_import(lambda: service.apply(command)))
