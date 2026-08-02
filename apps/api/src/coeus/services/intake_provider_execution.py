"""Execute frozen intake provider work behind admission controls."""

from typing import cast
from uuid import UUID

from coeus.application.ports.admission import ProviderAdmission
from coeus.core.errors import AppError
from coeus.domain.tickets import IntakeDetails
from coeus.services.conversation_reply_records import deterministic_reply
from coeus.services.intake import AdmittedAssistantReply, IntakeAssistantProvider
from coeus.services.intake_interpretation_provider import (
    AdmittedIntakeInterpretation,
    PreparedIntakeInterpretation,
)
from coeus.services.intake_planner import deterministic_intake_plan
from coeus.services.intake_planner_advice import render_intake_plan
from coeus.services.intake_provider_calls import PreparedIntakeReply


def execute_intake_reply(
    actor_user_id: UUID,
    provider: IntakeAssistantProvider,
    admission: ProviderAdmission | None,
    intake: IntakeDetails,
    safety_flags: tuple[str, ...],
) -> AdmittedAssistantReply:
    prepare_reply = cast(object, getattr(provider, "prepare_assistant_reply", None))
    if not callable(prepare_reply):
        if admission is not None:
            raise RuntimeError(
                "Providers used with admission must prepare an immutable intake reply."
            )
        return deterministic_reply(
            provider.build_assistant_message(intake, safety_flags),
            "safety_refusal" if safety_flags else "local_provider",
        )
    prepared = cast(PreparedIntakeReply, prepare_reply(intake, safety_flags))
    if not prepared.requires_admission:
        return prepared.execute()
    if admission is None:
        return prepared.admission_unavailable_reply
    with admission.reserve(actor_user_id) as reservation:
        outcome = prepared.execute()
        if outcome.provider_succeeded:
            reservation.commit()
        return outcome


def execute_intake_interpretation(
    actor_user_id: UUID,
    provider: IntakeAssistantProvider,
    admission: ProviderAdmission | None,
    current_answer: str,
    target_field: str,
) -> AdmittedIntakeInterpretation | None:
    prepare = cast(object, getattr(provider, "prepare_intake_interpretation", None))
    if not callable(prepare):
        return None
    prepared = cast(
        PreparedIntakeInterpretation | None,
        prepare(current_answer, target_field),
    )
    if prepared is None:
        return None
    if not prepared.requires_admission:
        return prepared.execute()
    if admission is None:
        return prepared.admission_unavailable_reply
    try:
        with admission.reserve(actor_user_id) as reservation:
            outcome = prepared.execute()
            if outcome.provider_succeeded:
                reservation.commit()
            return outcome
    except AppError as error:
        if error.code != "provider_capacity_exhausted":
            raise
        return prepared.admission_unavailable_reply


def execute_planned_intake_reply(
    actor_user_id: UUID,
    provider: IntakeAssistantProvider,
    admission: ProviderAdmission | None,
    intake: IntakeDetails,
    *,
    use_provider: bool,
) -> AdmittedAssistantReply:
    if use_provider:
        return execute_intake_reply(actor_user_id, provider, admission, intake, ())
    plan = deterministic_intake_plan(intake, intake.missing_information)
    return deterministic_reply(render_intake_plan(plan, intake), "local_provider")
