from collections.abc import Iterable
from uuid import UUID

from coeus.api.presenters.advisory_agents import advice_response
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.tickets import (
    AgentRun,
    AttachmentMetadata,
    ChatMessage,
    ClarificationRequest,
    IntakeDetails,
    TicketCollaborator,
    TicketRecord,
    TicketTimelineEntry,
)
from coeus.schemas.tickets import (
    AgentRunResponse,
    AttachmentMetadataResponse,
    ChatMessageResponse,
    ClarificationResponse,
    CollaboratorResponse,
    CustomerEstimateResponse,
    CustomerJourneyStageResponse,
    CustomerStatusResponse,
    DirectoryResponse,
    DirectoryUserResponse,
    IntakeChecklistItemResponse,
    IntakeDetailsResponse,
    TicketResponse,
    TicketSummaryResponse,
    TimelineEntryResponse,
)
from coeus.services.customer_projection import customer_clarifications, customer_timeline
from coeus.services.customer_status import CustomerStatus, customer_status
from coeus.services.intake_planner import intake_is_ready_for_submission
from coeus.services.intake_standard import applicable_entries, entry_satisfied, entry_value
from coeus.services.rfi_result_projection import project_rfi_result_signal


def to_ticket_response(
    ticket: TicketRecord,
    actor: UserAccount,
    visible_rfi_product_ids: frozenset[UUID] | None = None,
) -> TicketResponse:
    staff_view = Permission.TICKET_READ_ALL in actor.permissions
    ticket = project_rfi_result_signal(
        ticket,
        visible_rfi_product_ids or frozenset(),
        preserve_full=(
            ticket.requester_user_id == actor.user_id
            or (visible_rfi_product_ids is None and staff_view)
        ),
    )
    status = customer_status(ticket, actor)
    clarifications = (
        ticket.clarification_requests if staff_view else customer_clarifications(ticket)
    )
    history = ticket.timeline if staff_view else customer_timeline(ticket)
    return TicketResponse(
        ticket_id=ticket.ticket_id,
        reference=ticket.reference,
        requester_user_id=ticket.requester_user_id,
        state=ticket.state.value,
        customer_status=_to_customer_status(status),
        intake=_to_intake_response(ticket.intake),
        intake_checklist=_to_intake_checklist(ticket.intake),
        conversation_status=ticket.conversation_status,
        collect_disposition=ticket.collect_disposition,
        is_ready_for_submission=intake_is_ready_for_submission(ticket.intake),
        visible_product_matches=_visible_product_matches(ticket, actor),
        released_product_ids=[dissemination.product_id for dissemination in ticket.disseminations],
        collaborators=[
            _to_collaborator_response(collaborator) for collaborator in ticket.collaborators
        ],
        messages=[_to_message_response(message) for message in ticket.messages],
        attachments=[_to_attachment_response(attachment) for attachment in ticket.attachments],
        agent_runs=[to_agent_run_response(run) for run in ticket.agent_runs] if staff_view else [],
        clarification_requests=[_to_clarification_response(item) for item in clarifications],
        timeline=[_to_timeline_response(entry) for entry in history],
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


def to_ticket_summary_response(
    ticket: TicketRecord,
    actor: UserAccount,
    visible_rfi_product_ids: frozenset[UUID] | None = None,
) -> TicketSummaryResponse:
    ticket = project_rfi_result_signal(
        ticket,
        visible_rfi_product_ids or frozenset(),
        preserve_full=(
            ticket.requester_user_id == actor.user_id
            or (visible_rfi_product_ids is None and Permission.TICKET_READ_ALL in actor.permissions)
        ),
    )
    return TicketSummaryResponse(
        ticket_id=ticket.ticket_id,
        reference=ticket.reference,
        requester_user_id=ticket.requester_user_id,
        state=ticket.state.value,
        customer_status=_to_customer_status(customer_status(ticket, actor)),
        title=ticket.intake.title,
        priority=ticket.intake.priority,
        is_ready_for_submission=intake_is_ready_for_submission(ticket.intake),
        collaborator_count=len(ticket.collaborators),
        released_product_id=(
            ticket.disseminations[-1].product_id if ticket.disseminations else None
        ),
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


def to_directory_response(users: Iterable[UserAccount]) -> DirectoryResponse:
    return DirectoryResponse(
        users=[
            DirectoryUserResponse(
                user_id=user.user_id,
                username=user.username,
                display_name=user.display_name,
            )
            for user in users
        ]
    )


def _visible_product_matches(ticket: TicketRecord, actor: UserAccount) -> list[str]:
    if ticket.requester_user_id != actor.user_id:
        return []
    return list(ticket.visible_product_matches)


def _to_customer_status(status: CustomerStatus) -> CustomerStatusResponse:
    estimate = status.estimate
    return CustomerStatusResponse(
        code=status.code,
        label=status.label,
        explanation=status.explanation,
        current_leg=status.current_leg,
        action_required=status.action_required,
        action_type=status.action_type,
        next_milestone=status.next_milestone,
        canonical_ticket_id=status.canonical_ticket_id,
        estimate=CustomerEstimateResponse(
            earliest=estimate.earliest,
            likely=estimate.likely,
            latest=estimate.latest,
            confidence=estimate.confidence,
            status=estimate.status,
            as_of=estimate.as_of,
            policy_version=estimate.policy_version,
        )
        if estimate
        else None,
        journey=[
            CustomerJourneyStageResponse(code=item.code, label=item.label, status=item.status)
            for item in status.journey
        ],
    )


def _to_intake_checklist(intake: IntakeDetails) -> list[IntakeChecklistItemResponse]:
    # The applicable standard entries are the single source of truth for the
    # workspace checklist, so the urgency entries appear only when relevant.
    return [
        IntakeChecklistItemResponse(
            key=entry.field,
            label=entry.label,
            value=entry_value(entry, intake),
            satisfied=entry_satisfied(entry, intake),
        )
        for entry in applicable_entries(intake.priority)
    ]


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
        suggested_acg_context=intake.suggested_acg_context,
        requesting_unit=intake.requesting_unit,
        intelligence_disciplines=intake.intelligence_disciplines,
        supported_operation=intake.supported_operation,
        urgency_justification=intake.urgency_justification,
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


def to_agent_run_response(run: AgentRun) -> AgentRunResponse:
    return AgentRunResponse(
        run_id=run.run_id,
        agent_name=run.agent_name,
        status=run.status.value,
        summary=run.summary,
        safety_flags=list(run.safety_flags),
        execution_kind=run.execution_kind.value if run.execution_kind else None,
        provider=run.provider,
        model=run.model,
        duration_ms=run.duration_ms,
        fallback_outcome=run.fallback_outcome,
        validation_outcome=run.validation_outcome,
        prompt_version=run.prompt_version,
        policy_version=run.policy_version,
        context_schema_version=run.context_schema_version,
        input_hash=run.input_hash,
        output_hash=run.output_hash,
        input_token_count=run.input_token_count,
        output_token_count=run.output_token_count,
        error_class=run.error_class,
        advice=advice_response(run.advice) if run.advice else None,
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
