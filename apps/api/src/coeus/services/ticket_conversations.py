from contextlib import nullcontext
from dataclasses import replace
from datetime import UTC, datetime
from typing import Protocol, cast
from uuid import UUID, uuid4

from coeus.application.ports.admission import ProviderAdmission, TicketAdmission
from coeus.application.ports.tickets import TicketRepository
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.core.resource_limits import (
    MAX_ASSISTANT_REPLY_BYTES,
    MAX_CHAT_HISTORY_BYTES,
    MAX_CHAT_MESSAGES_PER_TICKET,
    text_bytes,
)
from coeus.domain.agent_names import INTAKE_PLANNER_AGENT
from coeus.domain.auth import AuthenticatedSession, UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.tickets import (
    AgentExecutionKind,
    AgentRun,
    AgentRunStatus,
    IntakeDetails,
    MessageAuthor,
    TicketRecord,
)
from coeus.domain.workflow_authority import WorkflowCommitAuthority
from coeus.services import conversation_lifecycle as lifecycle
from coeus.services.audit import AuditLog
from coeus.services.conversation_reply_records import (
    advice_for_reply,
    deterministic_reply,
    text_hash,
)
from coeus.services.intake import (
    AdmittedAssistantReply,
    IntakeAssistantProvider,
    IntakeExtractionService,
)
from coeus.services.intake_planner import deterministic_intake_plan
from coeus.services.intake_planner_advice import render_intake_plan
from coeus.services.intake_provider_calls import PreparedIntakeReply
from coeus.services.intake_standard import next_elicitation
from coeus.services.intake_transcripts import requester_message
from coeus.services.prioritisation import with_assessment
from coeus.services.ticket_mutations import TicketMutationService
from coeus.services.ticket_records import message as message_record
from coeus.services.ticket_records import timeline


class ConversationTicketService(Protocol):
    def get_editable_ticket(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        pass

    def state_for_intake(self, current_state: TicketState, intake: IntakeDetails) -> TicketState:
        pass


class ConversationService:
    def __init__(
        self,
        repository: TicketRepository,
        tickets: ConversationTicketService,
        mutations: TicketMutationService,
        extractor: IntakeExtractionService,
        llm_provider: IntakeAssistantProvider,
        audit_log: AuditLog,
        provider_admission: ProviderAdmission | None = None,
        ticket_admission: TicketAdmission | None = None,
    ) -> None:
        self._repository = repository
        self._tickets = tickets
        self._mutations = mutations
        self._extractor = extractor
        self._llm_provider = llm_provider
        self._audit_log = audit_log
        self._provider_admission = provider_admission
        self._ticket_admission = ticket_admission

    def send_message(
        self,
        authenticated: AuthenticatedSession,
        message: str,
        ticket_id: UUID | None = None,
    ) -> TicketRecord:
        actor = authenticated.user
        reservation = (
            self._ticket_admission.reserve(actor.user_id)
            if ticket_id is None and self._ticket_admission is not None
            else nullcontext(None)
        )
        with reservation as reference:
            ticket = (
                self._tickets.get_editable_ticket(actor, ticket_id)
                if ticket_id
                else self._create(actor, reference)
            )
            return self._send_to_ticket(
                actor,
                message,
                ticket,
                WorkflowCommitAuthority(
                    actor,
                    authenticated.session,
                    frozenset({Permission.CHAT_USE}),
                ),
                create=ticket_id is None,
            )

    def reopen(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        ticket = self._tickets.get_editable_ticket(actor, ticket_id)
        if ticket.conversation_status != lifecycle.CONVERSATION_CLOSED:
            raise AppError(
                409,
                "conversation_not_closed",
                "The intake conversation is already open.",
            )
        proposed = replace(
            ticket,
            conversation_status=lifecycle.CONVERSATION_OPEN,
            timeline=(
                *ticket.timeline,
                timeline(
                    ticket.ticket_id,
                    actor.user_id,
                    "conversation_reopened",
                    "Intake conversation reopened.",
                ),
            ),
        )
        return self._mutations.save_audited_if_current(
            ticket,
            proposed,
            "ticket_conversation_reopened",
            actor,
            {"ticket_id": str(ticket.ticket_id)},
        )

    def _send_to_ticket(
        self,
        actor: UserAccount,
        message: str,
        ticket: TicketRecord,
        authority: WorkflowCommitAuthority,
        *,
        create: bool = False,
    ) -> TicketRecord:
        if ticket.conversation_status == lifecycle.CONVERSATION_CLOSED:
            raise AppError(
                409,
                "conversation_closed",
                "The intake conversation is complete. Review the details and submit.",
            )
        self._ensure_chat_budget(ticket, message)
        user_message = message_record(ticket.ticket_id, MessageAuthor.USER, message)
        safety_flags = self._extractor.safety_flags_for(message)
        # Flagged messages are never extracted, so injected text cannot land
        # in intake fields; the message, flags and refusal are still recorded.
        intake = ticket.intake if safety_flags else self._extractor.extract(message, ticket.intake)
        if safety_flags:
            assistant_reply = self._assistant_reply(actor, intake, safety_flags)
            conversation_status = ticket.conversation_status
        else:
            assistant_reply, conversation_status = self._reply_and_status(
                actor,
                ticket.conversation_status,
                requester_message(message),
                intake,
            )
        reply = assistant_reply.text
        if text_bytes(reply) > MAX_ASSISTANT_REPLY_BYTES:
            raise AppError(
                502,
                "assistant_reply_limit_exceeded",
                "The assistant returned an invalid response.",
            )
        assistant_message = message_record(ticket.ticket_id, MessageAuthor.ASSISTANT, reply)
        if self._chat_bytes(ticket) + text_bytes(message, reply) > MAX_CHAT_HISTORY_BYTES:
            raise AppError(409, "chat_history_limit_reached", "The chat history limit was reached.")
        agent_run = AgentRun(
            run_id=uuid4(),
            ticket_id=ticket.ticket_id,
            agent_name=INTAKE_PLANNER_AGENT,
            status=AgentRunStatus.COMPLETED,
            summary=(
                "Message flagged; intake extraction skipped."
                if safety_flags
                else "Structured intake fields extracted from user chat."
            ),
            safety_flags=safety_flags,
            created_at=datetime.now(UTC),
            execution_kind=(
                AgentExecutionKind.PROVIDER_BACKED
                if assistant_reply.provider is not None or assistant_reply.provider_succeeded
                else AgentExecutionKind.DETERMINISTIC
            ),
            provider=assistant_reply.provider,
            model=assistant_reply.model,
            duration_ms=assistant_reply.duration_ms,
            fallback_outcome=assistant_reply.fallback_outcome,
            validation_outcome=assistant_reply.validation_outcome,
            prompt_version=assistant_reply.prompt_version,
            policy_version=assistant_reply.policy_version or "intake-conversation-v1",
            context_schema_version=(assistant_reply.context_schema_version or "intake-details-v1"),
            input_hash=assistant_reply.input_hash or text_hash(message),
            output_hash=assistant_reply.output_hash or text_hash(reply),
            input_token_count=assistant_reply.input_tokens,
            output_token_count=assistant_reply.output_tokens,
            error_class=assistant_reply.error_class,
            advice=advice_for_reply(assistant_reply),
        )
        state = self._tickets.state_for_intake(ticket.state, intake)
        proposed = with_assessment(
            replace(
                ticket,
                state=state,
                intake=intake,
                conversation_status=conversation_status,
                messages=(*ticket.messages, user_message, assistant_message),
                agent_runs=(*ticket.agent_runs, agent_run),
                timeline=(
                    *ticket.timeline,
                    timeline(
                        ticket.ticket_id, actor.user_id, "chat_message", "User chat received."
                    ),
                ),
            )
        )
        if create:
            return self._mutations.create_authorised_audited(
                proposed,
                "ticket_chat_message_received",
                authority,
                {"ticket_id": str(ticket.ticket_id)},
            )
        return self._mutations.save_authorised_audited_if_current(
            ticket,
            proposed,
            "ticket_chat_message_received",
            authority,
            {"ticket_id": str(ticket.ticket_id)},
        )

    @staticmethod
    def _chat_bytes(ticket: TicketRecord) -> int:
        return sum(text_bytes(item.body) for item in ticket.messages)

    def _ensure_chat_budget(self, ticket: TicketRecord, message: str) -> None:
        if len(ticket.messages) + 2 > MAX_CHAT_MESSAGES_PER_TICKET:
            raise AppError(409, "chat_history_limit_reached", "The chat history limit was reached.")
        projected = self._chat_bytes(ticket) + text_bytes(message) + MAX_ASSISTANT_REPLY_BYTES
        if projected > MAX_CHAT_HISTORY_BYTES:
            raise AppError(409, "chat_history_limit_reached", "The chat history limit was reached.")

    def _reply_and_status(
        self, actor: UserAccount, status: str, message: str, intake: IntakeDetails
    ) -> tuple[AdmittedAssistantReply, str]:
        """Deterministic conversation lifecycle; the LLM never decides this."""
        plan = deterministic_intake_plan(intake, intake.missing_information)
        blocked = bool(plan.contradictions)
        complete = not intake.missing_information and not blocked
        offered = status == lifecycle.CONVERSATION_CLOSE_OFFERED
        if offered and complete and lifecycle.confirms_close(message):
            reply = deterministic_reply(lifecycle.CLOSED_MESSAGE, "conversation_closed")
            return reply, lifecycle.CONVERSATION_CLOSED
        if lifecycle.wants_to_end(message):
            if complete:
                return deterministic_reply(
                    lifecycle.CLOSED_MESSAGE, "conversation_closed"
                ), lifecycle.CONVERSATION_CLOSED
            if blocked:
                question = render_intake_plan(plan, intake)
            else:
                entry = next_elicitation(intake.missing_information)
                question = entry.question if entry else ""
            return (
                deterministic_reply(
                    lifecycle.cannot_close_message(question).strip(),
                    (
                        "close_refused_intake_contradiction"
                        if blocked
                        else "close_refused_missing_information"
                    ),
                ),
                lifecycle.CONVERSATION_OPEN,
            )
        if blocked or plan.ambiguities:
            return self._assistant_reply(actor, intake, ()), lifecycle.CONVERSATION_OPEN
        if complete:
            return deterministic_reply(
                lifecycle.CLOSE_OFFER_MESSAGE, "close_offered"
            ), lifecycle.CONVERSATION_CLOSE_OFFERED
        return (
            self._assistant_reply(actor, intake, ()),
            lifecycle.CONVERSATION_OPEN,
        )

    def _assistant_reply(
        self, actor: UserAccount, intake: IntakeDetails, safety_flags: tuple[str, ...]
    ) -> AdmittedAssistantReply:
        prepare_reply = cast(
            object,
            getattr(self._llm_provider, "prepare_assistant_reply", None),
        )
        if not callable(prepare_reply):
            if self._provider_admission is not None:
                raise RuntimeError(
                    "Providers used with admission must prepare an immutable intake reply."
                )
            return deterministic_reply(
                self._llm_provider.build_assistant_message(intake, safety_flags),
                "safety_refusal" if safety_flags else "local_provider",
            )
        prepared = cast(PreparedIntakeReply, prepare_reply(intake, safety_flags))
        if not prepared.requires_admission:
            return prepared.execute()
        if self._provider_admission is None:
            return prepared.admission_unavailable_reply
        with self._provider_admission.reserve(actor.user_id) as reservation:
            outcome = prepared.execute()
            if outcome.provider_succeeded:
                reservation.commit()
            return outcome

    def _create(self, actor: UserAccount, reserved_reference: str | None = None) -> TicketRecord:
        ticket_id = uuid4()
        return TicketRecord(
            ticket_id=ticket_id,
            reference=reserved_reference or self._repository.next_reference(),
            requester_user_id=actor.user_id,
            state=TicketState.DRAFT_INTAKE,
            intake=IntakeDetails(),
            timeline=(
                timeline(ticket_id, actor.user_id, "ticket_created", "Draft intake started."),
            ),
        )
