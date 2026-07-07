from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from coeus.api.dependencies import (
    get_csrf_validated_session,
    get_current_session,
    get_ticket_collaborator_service,
    get_ticket_lifecycle_service,
    get_ticket_services,
    require_permission,
)
from coeus.core.permissions import Permission
from coeus.domain.auth import AuthenticatedSession, UserAccount
from coeus.domain.tickets import (
    AgentRun,
    AttachmentMetadata,
    ChatMessage,
    ClarificationRequest,
    CollaboratorAccess,
    IntakeDetails,
    TicketCollaborator,
    TicketRecord,
    TicketTimelineEntry,
)
from coeus.schemas.tickets import (
    AddInformationRequest,
    AgentRunResponse,
    AttachmentMetadataRequest,
    AttachmentMetadataResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ClarificationResponse,
    CollaboratorAddRequest,
    CollaboratorResponse,
    DirectoryResponse,
    DirectoryUserResponse,
    IntakeDetailsResponse,
    IntakeUpdateRequest,
    TicketCancelRequest,
    TicketListResponse,
    TicketResponse,
    TimelineEntryResponse,
)
from coeus.services.ticket_collaborators import TicketCollaboratorService
from coeus.services.ticket_lifecycle import TicketLifecycleService
from coeus.services.tickets import TicketServices

router = APIRouter(tags=["tickets"])


@router.get("/tickets", response_model=TicketListResponse)
async def list_tickets(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    ticket_services: Annotated[TicketServices, Depends(get_ticket_services)],
) -> TicketListResponse:
    return TicketListResponse(
        tickets=[
            _to_ticket_response(ticket, authenticated.user)
            for ticket in ticket_services.tickets.list_visible_tickets(authenticated.user)
        ]
    )


# Plain def so FastAPI runs this handler in the threadpool: the assistant
# reply may call the Gemini HTTP API synchronously and must not block the
# event loop.
@router.post("/chat/messages", response_model=TicketResponse, status_code=201)
def send_chat_message(
    payload: ChatMessageRequest,
    authenticated: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.CHAT_USE)),
    ],
    ticket_services: Annotated[TicketServices, Depends(get_ticket_services)],
    _csrf_session: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
) -> TicketResponse:
    ticket = ticket_services.conversations.send_message(
        authenticated.user,
        payload.message,
        payload.ticket_id,
    )
    return _to_ticket_response(ticket, authenticated.user)


@router.patch("/tickets/{ticket_id}/intake", response_model=TicketResponse)
async def update_intake(
    ticket_id: UUID,
    payload: IntakeUpdateRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    ticket_services: Annotated[TicketServices, Depends(get_ticket_services)],
) -> TicketResponse:
    updates = {
        key: value
        for key, value in payload.model_dump(exclude_unset=True).items()
        if value is not None
    }
    return _to_ticket_response(
        ticket_services.tickets.update_intake(authenticated.user, ticket_id, updates),
        authenticated.user,
    )


@router.post("/tickets/{ticket_id}/attachments", response_model=TicketResponse)
async def add_attachment(
    ticket_id: UUID,
    payload: AttachmentMetadataRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    ticket_services: Annotated[TicketServices, Depends(get_ticket_services)],
) -> TicketResponse:
    ticket = ticket_services.tickets.add_attachment(
        authenticated.user,
        ticket_id,
        payload.name,
        payload.description,
        payload.source_type,
    )
    return _to_ticket_response(ticket, authenticated.user)


@router.post("/tickets/{ticket_id}/submit", response_model=TicketResponse)
async def submit_ticket(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    ticket_services: Annotated[TicketServices, Depends(get_ticket_services)],
) -> TicketResponse:
    return _to_ticket_response(
        ticket_services.tickets.submit(authenticated.user, ticket_id),
        authenticated.user,
    )


@router.get("/users/directory", response_model=DirectoryResponse)
async def user_directory(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    collaborators: Annotated[TicketCollaboratorService, Depends(get_ticket_collaborator_service)],
    q: Annotated[str, Query(min_length=3, max_length=254)],
) -> DirectoryResponse:
    return DirectoryResponse(
        users=[
            DirectoryUserResponse(
                user_id=user.user_id,
                username=user.username,
                display_name=user.display_name,
            )
            for user in collaborators.directory(authenticated.user, q)
        ]
    )


@router.post("/tickets/{ticket_id}/collaborators", response_model=TicketResponse)
async def add_collaborator(
    ticket_id: UUID,
    payload: CollaboratorAddRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    collaborators: Annotated[TicketCollaboratorService, Depends(get_ticket_collaborator_service)],
) -> TicketResponse:
    ticket = collaborators.add(
        authenticated.user,
        ticket_id,
        payload.username,
        CollaboratorAccess(payload.access),
    )
    return _to_ticket_response(ticket, authenticated.user)


@router.delete("/tickets/{ticket_id}/collaborators/{user_id}", response_model=TicketResponse)
async def remove_collaborator(
    ticket_id: UUID,
    user_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    collaborators: Annotated[TicketCollaboratorService, Depends(get_ticket_collaborator_service)],
) -> TicketResponse:
    return _to_ticket_response(
        collaborators.remove(authenticated.user, ticket_id, user_id),
        authenticated.user,
    )


@router.post("/tickets/{ticket_id}/cancel", response_model=TicketResponse)
async def cancel_ticket(
    ticket_id: UUID,
    payload: TicketCancelRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    lifecycle: Annotated[TicketLifecycleService, Depends(get_ticket_lifecycle_service)],
) -> TicketResponse:
    return _to_ticket_response(
        lifecycle.cancel(authenticated.user, ticket_id, payload.reason),
        authenticated.user,
    )


@router.post("/tickets/{ticket_id}/confirm-delivery", response_model=TicketResponse)
async def confirm_delivery(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    lifecycle: Annotated[TicketLifecycleService, Depends(get_ticket_lifecycle_service)],
) -> TicketResponse:
    return _to_ticket_response(
        lifecycle.confirm_delivery(authenticated.user, ticket_id),
        authenticated.user,
    )


@router.post("/tickets/{ticket_id}/timeline", response_model=TicketResponse)
async def add_information(
    ticket_id: UUID,
    payload: AddInformationRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    ticket_services: Annotated[TicketServices, Depends(get_ticket_services)],
) -> TicketResponse:
    ticket = ticket_services.tickets.add_information(authenticated.user, ticket_id, payload.body)
    return _to_ticket_response(ticket, authenticated.user)


def _to_ticket_response(ticket: TicketRecord, actor: UserAccount) -> TicketResponse:
    return TicketResponse(
        ticket_id=ticket.ticket_id,
        reference=ticket.reference,
        requester_user_id=ticket.requester_user_id,
        state=ticket.state.value,
        intake=_to_intake_response(ticket.intake),
        is_ready_for_submission=not ticket.intake.missing_information,
        suggested_project_name=ticket.suggested_project_name,
        visible_product_matches=_visible_product_matches(ticket, actor),
        released_product_ids=[dissemination.product_id for dissemination in ticket.disseminations],
        collaborators=[
            _to_collaborator_response(collaborator) for collaborator in ticket.collaborators
        ],
        messages=[_to_message_response(message) for message in ticket.messages],
        attachments=[_to_attachment_response(attachment) for attachment in ticket.attachments],
        agent_runs=[_to_agent_run_response(run) for run in ticket.agent_runs],
        clarification_requests=[
            _to_clarification_response(item) for item in ticket.clarification_requests
        ],
        timeline=[_to_timeline_response(entry) for entry in ticket.timeline],
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


def _visible_product_matches(ticket: TicketRecord, actor: UserAccount) -> list[str]:
    if ticket.requester_user_id != actor.user_id:
        return []
    return list(ticket.visible_product_matches)


def _to_intake_response(intake: IntakeDetails) -> IntakeDetailsResponse:
    return IntakeDetailsResponse(
        title=intake.title,
        description=intake.description,
        operational_question=intake.operational_question,
        area_or_region=intake.area_or_region,
        time_period_start=intake.time_period_start,
        time_period_end=intake.time_period_end,
        priority=intake.priority,
        deadline=intake.deadline,
        required_output_format=intake.required_output_format,
        known_context=intake.known_context,
        restrictions_or_caveats=intake.restrictions_or_caveats,
        customer_success_criteria=intake.customer_success_criteria,
        suggested_project_name=intake.suggested_project_name,
        suggested_acg_context=intake.suggested_acg_context,
        missing_information=list(intake.missing_information),
        confidence=intake.confidence,
    )


def _to_collaborator_response(collaborator: TicketCollaborator) -> CollaboratorResponse:
    return CollaboratorResponse(
        user_id=collaborator.user_id,
        username=collaborator.username,
        display_name=collaborator.display_name,
        access=collaborator.access.value,
        added_by_user_id=collaborator.added_by_user_id,
        created_at=collaborator.created_at,
    )


def _to_message_response(message: ChatMessage) -> ChatMessageResponse:
    return ChatMessageResponse(
        message_id=message.message_id,
        author=message.author.value,
        body=message.body,
        created_at=message.created_at,
    )


def _to_attachment_response(attachment: AttachmentMetadata) -> AttachmentMetadataResponse:
    return AttachmentMetadataResponse(
        attachment_id=attachment.attachment_id,
        name=attachment.name,
        description=attachment.description,
        source_type=attachment.source_type,
        created_at=attachment.created_at,
    )


def _to_agent_run_response(run: AgentRun) -> AgentRunResponse:
    return AgentRunResponse(
        run_id=run.run_id,
        agent_name=run.agent_name,
        status=run.status.value,
        summary=run.summary,
        safety_flags=list(run.safety_flags),
        created_at=run.created_at,
    )


def _to_clarification_response(item: ClarificationRequest) -> ClarificationResponse:
    return ClarificationResponse(
        clarification_id=item.clarification_id,
        route=item.route.value,
        reason=item.reason,
        questions=list(item.questions),
        created_at=item.created_at,
    )


def _to_timeline_response(entry: TicketTimelineEntry) -> TimelineEntryResponse:
    return TimelineEntryResponse(
        entry_id=entry.entry_id,
        event_type=entry.event_type,
        body=entry.body,
        actor_user_id=entry.actor_user_id,
        created_at=entry.created_at,
    )
