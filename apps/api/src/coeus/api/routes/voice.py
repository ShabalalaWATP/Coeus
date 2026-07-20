import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from coeus.api.dependencies import (
    get_csrf_validated_session,
    get_ticket_services,
    get_voice_model_service,
    get_voice_session_service,
    require_permission,
)
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import AuthenticatedSession
from coeus.schemas.voice import (
    VoiceApiKeyUpdateRequest,
    VoiceConnectionTestResponse,
    VoiceModelStateResponse,
    VoiceModelUpdateRequest,
)
from coeus.services.tickets import TicketServices
from coeus.services.voice_models import VoiceModelService, VoiceModelState
from coeus.services.voice_sessions import MAX_SDP_BYTES, VoiceSessionService

router = APIRouter(tags=["voice"])


@router.get("/admin/voice-model", response_model=VoiceModelStateResponse)
def admin_voice_model(
    permitted: Annotated[
        AuthenticatedSession, Depends(require_permission(Permission.SYSTEM_CONFIGURE))
    ],
    service: Annotated[VoiceModelService, Depends(get_voice_model_service)],
) -> VoiceModelStateResponse:
    return _response(service.state())


@router.put("/admin/voice-model", response_model=VoiceModelStateResponse)
def configure_voice_model(
    payload: VoiceModelUpdateRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    permitted: Annotated[
        AuthenticatedSession, Depends(require_permission(Permission.SYSTEM_CONFIGURE))
    ],
    service: Annotated[VoiceModelService, Depends(get_voice_model_service)],
) -> VoiceModelStateResponse:
    return _response(
        service.configure(
            str(authenticated.user.user_id),
            authenticated.user.username,
            payload.model,
            payload.enabled,
        )
    )


@router.put("/admin/voice-model/api-key", response_model=VoiceModelStateResponse)
def configure_voice_api_key(
    payload: VoiceApiKeyUpdateRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    permitted: Annotated[
        AuthenticatedSession, Depends(require_permission(Permission.SYSTEM_CONFIGURE))
    ],
    service: Annotated[VoiceModelService, Depends(get_voice_model_service)],
) -> VoiceModelStateResponse:
    return _response(
        service.configure_api_key(
            str(authenticated.user.user_id), authenticated.user.username, payload.api_key
        )
    )


@router.post("/admin/voice-model/test", response_model=VoiceConnectionTestResponse)
def test_voice_connection(
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    permitted: Annotated[
        AuthenticatedSession, Depends(require_permission(Permission.SYSTEM_CONFIGURE))
    ],
    service: Annotated[VoiceModelService, Depends(get_voice_model_service)],
) -> VoiceConnectionTestResponse:
    del authenticated, permitted
    result = service.test_connection()
    return VoiceConnectionTestResponse(
        ok=result.ok,
        provider=result.provider,
        model=result.model,
        message=result.message,
    )


@router.get("/voice/config", response_model=VoiceModelStateResponse)
def voice_config(
    permitted: Annotated[AuthenticatedSession, Depends(require_permission(Permission.CHAT_USE))],
    service: Annotated[VoiceModelService, Depends(get_voice_model_service)],
) -> VoiceModelStateResponse:
    return _response(service.state())


@router.post("/voice/session", response_class=Response)
async def create_voice_session(
    request: Request,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    permitted: Annotated[AuthenticatedSession, Depends(require_permission(Permission.CHAT_USE))],
    service: Annotated[VoiceSessionService, Depends(get_voice_session_service)],
    ticket_services: Annotated[TicketServices, Depends(get_ticket_services)],
    ticket_id: Annotated[UUID | None, Query(alias="ticketId")] = None,
) -> Response:
    media_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if media_type != "application/sdp":
        raise AppError(415, "invalid_sdp_media_type", "An application/sdp offer is required.")
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_SDP_BYTES:
        raise AppError(413, "sdp_too_large", "The SDP offer is too large.")
    chunks: list[bytes] = []
    received = 0
    async for chunk in request.stream():
        received += len(chunk)
        if received > MAX_SDP_BYTES:
            raise AppError(413, "sdp_too_large", "The SDP offer is too large.")
        chunks.append(chunk)
    body = b"".join(chunks)
    try:
        sdp = body.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AppError(422, "invalid_sdp", "The SDP offer is invalid.") from exc
    if "\x00" in sdp or not sdp.startswith("v=0") or "m=audio" not in sdp:
        raise AppError(422, "invalid_sdp", "The SDP offer is invalid.")
    intake = None
    if ticket_id is not None:
        ticket = ticket_services.tickets.get_editable_ticket(authenticated.user, ticket_id)
        intake = ticket.intake
    started = await asyncio.to_thread(service.create, authenticated.user.user_id, sdp, intake)
    return Response(
        started.answer,
        media_type="application/sdp",
        headers={
            "Cache-Control": "no-store",
            "X-Voice-Session-Token": str(started.token),
        },
    )


@router.delete("/voice/session/{token}", status_code=204)
def release_voice_session(
    token: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    permitted: Annotated[AuthenticatedSession, Depends(require_permission(Permission.CHAT_USE))],
    service: Annotated[VoiceSessionService, Depends(get_voice_session_service)],
) -> Response:
    service.release(authenticated.user.user_id, token)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


def _response(state: VoiceModelState) -> VoiceModelStateResponse:
    return VoiceModelStateResponse(
        model=state.model,
        available_models=list(state.available_models),
        enabled=state.enabled,
        api_key_configured=state.api_key_configured,
    )
