"""Saved-view, template and privacy-safe work-update routes."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel

from coeus.api.dependencies import get_csrf_validated_session, get_current_session
from coeus.api.organisation_dependencies import get_workspace_productivity
from coeus.core.errors import AppError
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.workspace_productivity import (
    ProductivityCommand,
    WorkspaceRecordConflict,
    WorkspaceRecordDenied,
)
from coeus.schemas.workspace_productivity import (
    AcknowledgeUpdatePayload,
    DeleteRecordPayload,
    DeleteTemplatePayload,
    PreferencesResponse,
    SavedViewPage,
    SavedViewResponse,
    SavePreferencesPayload,
    SaveStoreLinkPayload,
    SaveTemplatePayload,
    SaveViewPayload,
    StoreLinkPage,
    StoreLinkResponse,
    TemplatePage,
    TemplateResponse,
    WorkUpdatePage,
    WorkUpdateResponse,
)
from coeus.services.workspace_productivity import WorkspaceProductivityService

router = APIRouter(prefix="/organisation", tags=["workspace productivity"])
ReadSession = Annotated[AuthenticatedSession, Depends(get_current_session)]
WriteSession = Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)]
Service = Annotated[WorkspaceProductivityService, Depends(get_workspace_productivity)]


@router.get("/saved-board-views", response_model=SavedViewPage)
async def list_saved_views(
    authenticated: ReadSession,
    service: Service,
    cursor: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> SavedViewPage:
    page = _call(lambda: service.list_views(authenticated.user.user_id, cursor, limit))
    return SavedViewPage(
        items=[SavedViewResponse.model_validate(item) for item in page.items],
        nextCursor=page.next_cursor,
    )


@router.put("/workspaces/{unit_id}/saved-board-views", response_model=SavedViewResponse)
async def save_view(
    unit_id: UUID,
    payload: SaveViewPayload,
    authenticated: WriteSession,
    service: Service,
) -> SavedViewResponse:
    command = _command(payload, authenticated.user.user_id, "save_view", unit_id=unit_id)
    return SavedViewResponse.model_validate(_call(lambda: service.save_view(command)))


@router.delete(
    "/workspaces/{unit_id}/saved-board-views/{view_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_view(
    unit_id: UUID,
    view_id: UUID,
    payload: DeleteRecordPayload,
    authenticated: WriteSession,
    service: Service,
) -> Response:
    command = _command(
        payload,
        authenticated.user.user_id,
        "delete_view",
        unit_id=unit_id,
        view_id=view_id,
    )
    _call(lambda: service.delete_view(command))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/workspaces/{unit_id}/package-templates", response_model=TemplatePage)
async def list_templates(
    unit_id: UUID,
    authenticated: ReadSession,
    service: Service,
    cursor: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> TemplatePage:
    page = _call(lambda: service.list_templates(authenticated.user.user_id, unit_id, cursor, limit))
    return TemplatePage(
        items=[TemplateResponse.model_validate(item) for item in page.items],
        nextCursor=page.next_cursor,
    )


@router.put("/workspaces/{unit_id}/package-templates", response_model=TemplateResponse)
async def save_template(
    unit_id: UUID,
    payload: SaveTemplatePayload,
    authenticated: WriteSession,
    service: Service,
) -> TemplateResponse:
    command = _command(payload, authenticated.user.user_id, "save_template", unit_id=unit_id)
    return TemplateResponse.model_validate(_call(lambda: service.save_template(command)))


@router.delete(
    "/workspaces/{unit_id}/package-templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_template(
    unit_id: UUID,
    template_id: UUID,
    payload: DeleteTemplatePayload,
    authenticated: WriteSession,
    service: Service,
) -> Response:
    command = _command(
        payload,
        authenticated.user.user_id,
        "delete_template",
        unit_id=unit_id,
        template_id=template_id,
    )
    _call(lambda: service.delete_template(command))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/work-updates", response_model=WorkUpdatePage)
async def list_updates(
    authenticated: ReadSession,
    service: Service,
    cursor: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    unacknowledged_only: Annotated[bool, Query(alias="unacknowledgedOnly")] = False,
) -> WorkUpdatePage:
    page = _call(
        lambda: service.list_updates(authenticated.user.user_id, cursor, limit, unacknowledged_only)
    )
    return WorkUpdatePage(
        items=[WorkUpdateResponse.model_validate(item) for item in page.items],
        nextCursor=page.next_cursor,
    )


@router.post("/work-updates/{update_id}/acknowledgements", response_model=WorkUpdateResponse)
async def acknowledge_update(
    update_id: UUID,
    payload: AcknowledgeUpdatePayload,
    authenticated: WriteSession,
    service: Service,
) -> WorkUpdateResponse:
    command = _command(
        payload,
        authenticated.user.user_id,
        "acknowledge_update",
        update_id=update_id,
    )
    return WorkUpdateResponse.model_validate(_call(lambda: service.acknowledge_update(command)))


@router.get("/work-update-preferences", response_model=PreferencesResponse)
async def get_preferences(authenticated: ReadSession, service: Service) -> PreferencesResponse:
    return PreferencesResponse.model_validate(
        _call(lambda: service.get_preferences(authenticated.user.user_id))
    )


@router.put("/work-update-preferences", response_model=PreferencesResponse)
async def save_preferences(
    payload: SavePreferencesPayload,
    authenticated: WriteSession,
    service: Service,
) -> PreferencesResponse:
    command = _command(payload, authenticated.user.user_id, "save_preferences")
    return PreferencesResponse.model_validate(_call(lambda: service.save_preferences(command)))


@router.get("/workspaces/{unit_id}/store-links", response_model=StoreLinkPage)
async def list_store_links(
    unit_id: UUID,
    source_type: Annotated[str, Query(pattern="^(ticket|work_package)$", alias="sourceType")],
    source_id: Annotated[UUID, Query(alias="sourceId")],
    authenticated: ReadSession,
    service: Service,
    cursor: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> StoreLinkPage:
    page = _call(
        lambda: service.list_store_links(
            authenticated.user, unit_id, source_type, source_id, cursor, limit
        )
    )
    return StoreLinkPage(
        items=[StoreLinkResponse.model_validate(item) for item in page.items],
        nextCursor=page.next_cursor,
    )


@router.put("/workspaces/{unit_id}/store-links", response_model=StoreLinkResponse)
async def save_store_link(
    unit_id: UUID,
    payload: SaveStoreLinkPayload,
    authenticated: WriteSession,
    service: Service,
) -> StoreLinkResponse:
    command = _command(payload, authenticated.user.user_id, "save_store_link", unit_id=unit_id)
    item = _call(lambda: service.save_store_link(authenticated.user, command))
    return StoreLinkResponse.model_validate(item)


@router.delete(
    "/workspaces/{unit_id}/store-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_store_link(
    unit_id: UUID,
    link_id: UUID,
    payload: DeleteRecordPayload,
    authenticated: WriteSession,
    service: Service,
) -> Response:
    command = _command(
        payload,
        authenticated.user.user_id,
        "delete_store_link",
        unit_id=unit_id,
        link_id=link_id,
    )
    _call(lambda: service.delete_store_link(command))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _command(
    payload: BaseModel, actor: UUID, operation: str, **extra: object
) -> ProductivityCommand:
    values = payload.model_dump(mode="python")
    command_id = UUID(str(values.pop("command_id")))
    idempotency_key = str(values.pop("idempotency_key"))
    return ProductivityCommand(command_id, idempotency_key, actor, operation, {**values, **extra})


def _call[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except WorkspaceRecordDenied as exc:
        raise AppError(
            404, "workspace_record_not_found", "Workspace record was not found."
        ) from exc
    except WorkspaceRecordConflict as exc:
        raise AppError(409, "workspace_record_conflict", str(exc)) from exc
    except ValueError as exc:
        raise AppError(422, "workspace_record_invalid", str(exc)) from exc
