"""Authenticated actor-only canonical personal work."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from coeus.api.dependencies import get_auth_service, get_current_session
from coeus.api.organisation_dependencies import get_my_work
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.my_work import MyWorkColumn, MyWorkIntegrityError
from coeus.schemas.my_work import MyWorkCardResponse, MyWorkPageResponse
from coeus.services.auth import AuthService
from coeus.services.my_work import MyWorkService

router = APIRouter(prefix="/organisation/workspaces/my-work", tags=["personal work"])


@router.get("", response_model=MyWorkPageResponse)
async def list_my_work(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    service: Annotated[MyWorkService, Depends(get_my_work)],
    include_completed: Annotated[bool, Query(alias="includeCompleted")] = False,
    column: MyWorkColumn | None = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MyWorkPageResponse:
    auth_service.require_permission(authenticated, Permission.ANALYST_WORK)
    try:
        page = service.list_my_work(
            authenticated.user.user_id,
            include_completed=include_completed,
            column=column,
            cursor=cursor,
            limit=limit,
        )
    except ValueError as error:
        raise AppError(422, "invalid_my_work_query", "The work query is invalid.") from error
    except MyWorkIntegrityError as error:
        raise AppError(
            503, "my_work_unavailable", "Your work is temporarily unavailable."
        ) from error
    return MyWorkPageResponse(
        cards=[MyWorkCardResponse(**vars(card)) for card in page.cards],
        asOf=page.as_of,
        nextCursor=page.next_cursor,
    )
