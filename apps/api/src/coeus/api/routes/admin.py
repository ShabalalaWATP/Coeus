from typing import Annotated

from fastapi import APIRouter, Depends

from coeus.api.dependencies import require_permission
from coeus.core.permissions import Permission
from coeus.domain.auth import AuthenticatedSession

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
