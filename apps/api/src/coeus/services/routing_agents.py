from datetime import UTC, datetime
from uuid import uuid4

from coeus.domain.tickets import (
    CmCapabilityReview,
    IntakeDetails,
    RfaCapabilityReview,
    TicketRecord,
)

ASSESSMENT_TERMS = frozenset(
    {"assessment", "assess", "brief", "briefing", "report", "estimate", "analysis"}
)
COLLECTION_TERMS = frozenset(
    {"collection", "collect", "sensor", "imagery", "source", "monitor", "surveillance"}
)
UNSUPPORTED_TERMS = frozenset({"mars", "martian", "unknown", "tbd", "unbounded"})


class RfaCapabilityAgent:
    def review(self, ticket: TicketRecord) -> RfaCapabilityReview:
        text = _intake_text(ticket.intake)
        terms = _terms(text)
        output_terms = _terms(ticket.intake.required_output_format or "")
        clarifications = _base_clarifications(ticket.intake, terms)
        assessment_signal = bool(terms.intersection(ASSESSMENT_TERMS))
        collection_output = bool(output_terms.intersection(COLLECTION_TERMS)) and not bool(
            output_terms.intersection(ASSESSMENT_TERMS)
        )
        collection_only = collection_output or (
            bool(terms.intersection(COLLECTION_TERMS)) and not assessment_signal
        )
        can_satisfy = not clarifications and assessment_signal and not collection_only
        confidence = _confidence(can_satisfy, assessment_signal, clarifications)
        risks = _risks(ticket.intake, terms)
        return RfaCapabilityReview(
            review_id=uuid4(),
            ticket_id=ticket.ticket_id,
            can_satisfy=can_satisfy,
            confidence=confidence,
            required_clarifications=clarifications,
            suggested_work_packages=_rfa_work_packages(ticket.intake) if can_satisfy else (),
            suggested_team_id="RFA-MOCK-REGIONAL" if can_satisfy else None,
            estimated_effort=_estimated_effort(ticket.intake.priority),
            risks=risks,
            manager_review_required=True,
            reasoning_summary=_rfa_reason(can_satisfy, assessment_signal, collection_only),
            created_at=datetime.now(UTC),
        )


class CmCapabilityAgent:
    def review(self, ticket: TicketRecord) -> CmCapabilityReview:
        text = _intake_text(ticket.intake)
        terms = _terms(text)
        clarifications = _base_clarifications(ticket.intake, terms)
        collection_signal = bool(terms.intersection(COLLECTION_TERMS))
        can_satisfy = not clarifications and collection_signal
        confidence = _confidence(can_satisfy, collection_signal, clarifications)
        risks = _risks(ticket.intake, terms)
        return CmCapabilityReview(
            review_id=uuid4(),
            ticket_id=ticket.ticket_id,
            can_satisfy=can_satisfy,
            confidence=confidence,
            required_clarifications=clarifications,
            suggested_collection_route="collection_coordination" if can_satisfy else None,
            suggested_collection_sources=_collection_sources(terms) if can_satisfy else (),
            estimated_effort=_estimated_effort(ticket.intake.priority),
            risks=risks,
            manager_review_required=True,
            reasoning_summary=_cm_reason(can_satisfy, collection_signal),
            created_at=datetime.now(UTC),
        )


def _intake_text(intake: IntakeDetails) -> str:
    values = (
        intake.title,
        intake.description,
        intake.operational_question,
        intake.area_or_region,
        intake.required_output_format,
        intake.known_context,
        intake.customer_success_criteria,
    )
    return " ".join(value for value in values if value).casefold()


def _terms(text: str) -> frozenset[str]:
    return frozenset(word.strip(".,:;()[]") for word in text.split())


def _base_clarifications(intake: IntakeDetails, terms: frozenset[str]) -> tuple[str, ...]:
    clarifications = list(intake.missing_information)
    if terms.intersection(UNSUPPORTED_TERMS):
        clarifications.append("Confirm a supported mock region and practical collection scope.")
    if intake.deadline is None and (intake.priority or "").casefold() == "critical":
        clarifications.append("Provide the deadline for critical priority routing.")
    return tuple(dict.fromkeys(clarifications))


def _confidence(can_satisfy: bool, signal_present: bool, clarifications: tuple[str, ...]) -> float:
    if clarifications:
        return 0.28
    if can_satisfy:
        return 0.86
    if signal_present:
        return 0.48
    return 0.34


def _risks(intake: IntakeDetails, terms: frozenset[str]) -> tuple[str, ...]:
    risks: list[str] = []
    if terms.intersection(COLLECTION_TERMS) and not intake.deadline:
        risks.append("Collection timing needs manager confirmation.")
    if (intake.restrictions_or_caveats or "").strip():
        risks.append("Requester restrictions require manager review.")
    return tuple(risks)


def _rfa_work_packages(intake: IntakeDetails) -> tuple[str, ...]:
    region = intake.area_or_region or "the nominated mock region"
    return (
        f"Validate the requirement and assumptions for {region}.",
        "Draft the assessment approach and evidence gaps.",
        "Prepare analyst assignment notes for Sprint 9.",
    )


def _collection_sources(terms: frozenset[str]) -> tuple[str, ...]:
    sources = ["collection manager coordination"]
    if "imagery" in terms:
        sources.append("mock imagery holdings")
    if "sensor" in terms:
        sources.append("mock sensor reporting")
    return tuple(sources)


def _estimated_effort(priority: str | None) -> str:
    return "1-2 days" if (priority or "").casefold() in {"critical", "high"} else "3-5 days"


def _rfa_reason(can_satisfy: bool, assessment_signal: bool, collection_only: bool) -> str:
    if can_satisfy:
        return "RFA can satisfy the request with assessment-led work packages."
    if collection_only:
        return "Request is collection-led and should fall back to collection management."
    if assessment_signal:
        return "RFA signal exists but clarifications are required before approval."
    return "No strong assessment signal was found in the intake."


def _cm_reason(can_satisfy: bool, collection_signal: bool) -> str:
    if can_satisfy:
        return "Collection management can satisfy the request through controlled tasking."
    if collection_signal:
        return "Collection signal exists but clarifications are required before approval."
    return "No strong collection signal was found in the intake."
