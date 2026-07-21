import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from coeus.domain.capabilities import CandidateTeam, CapabilityTeam
from coeus.domain.tickets import (
    CmCapabilityReview,
    IntakeDetails,
    RfaCapabilityReview,
    TicketRecord,
)
from coeus.services.capability_catalogue import CapabilityCataloguePort
from coeus.services.prioritisation import assessment_or_computed

ASSESSMENT_TERMS = frozenset(
    {
        "analyse",
        "analysis",
        "analyze",
        "assess",
        "assessment",
        "brief",
        "briefing",
        "estimate",
        "report",
    }
)
COLLECTION_TERMS = frozenset(
    {"collection", "collect", "sensor", "imagery", "source", "monitor", "surveillance"}
)
UNSUPPORTED_TERMS = frozenset({"mars", "martian", "tbd", "unbounded"})
NEGATION_TERMS = frozenset(
    {"avoid", "avoids", "avoiding", "neither", "never", "no", "not", "without"}
)
NEGATION_WINDOW = 3

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_ROUTING_TOKEN_PATTERN = re.compile(r"[a-z0-9]+|[.!?;,:]")
_CLAUSE_BOUNDARIES = frozenset(".!?;,:")
_CONTRACTION_PATTERN = re.compile(r"\b[a-z]+n['\u2019]t\b")


@dataclass(frozen=True)
class RecommendationInputs:
    disciplines: frozenset[str]
    region: str | None
    priority_tier: str | None


class RfaReviewAgent(Protocol):
    def review(self, ticket: TicketRecord) -> RfaCapabilityReview: ...


class CmReviewAgent(Protocol):
    def review(self, ticket: TicketRecord) -> CmCapabilityReview: ...


class RfaCapabilityAgent:
    def __init__(self, catalogue: CapabilityCataloguePort) -> None:
        self._catalogue = catalogue

    def review(self, ticket: TicketRecord) -> RfaCapabilityReview:
        text = _intake_text(ticket.intake)
        terms = _terms(text)
        clarifications = _base_clarifications(ticket.intake, terms)
        inputs = _recommendation_inputs(ticket)
        candidates = self._catalogue.recommend_rfa(
            terms,
            disciplines=inputs.disciplines,
            region=inputs.region,
            priority_tier=inputs.priority_tier,
        )
        team = self._team_or_triage(candidates)
        assessment_signal, assessment_negated = _signal_state(text, ASSESSMENT_TERMS)
        collection_signal, collection_negated = _signal_state(text, COLLECTION_TERMS)
        output_text = ticket.intake.required_output_format or ""
        collection_output, output_collection_negated = _signal_state(output_text, COLLECTION_TERMS)
        assessment_output, output_assessment_negated = _signal_state(output_text, ASSESSMENT_TERMS)
        collection_output = collection_output and not assessment_output
        collection_only = collection_output or (collection_signal and not assessment_signal)
        can_satisfy = not clarifications and assessment_signal and not collection_only
        confidence = _evidence_strength(can_satisfy, assessment_signal, clarifications)
        negated_signal = any(
            (
                assessment_negated,
                collection_negated,
                output_collection_negated,
                output_assessment_negated,
            )
        )
        risks = _risks(ticket.intake, terms, negated_signal)
        return RfaCapabilityReview(
            review_id=uuid4(),
            ticket_id=ticket.ticket_id,
            can_satisfy=can_satisfy,
            confidence=confidence,
            required_clarifications=clarifications,
            suggested_work_packages=_rfa_work_packages(ticket.intake, team.name)
            if can_satisfy
            else (),
            suggested_team_id=team.team_id if can_satisfy else None,
            estimated_effort=_estimated_effort(ticket.intake.priority),
            risks=risks,
            manager_review_required=True,
            reasoning_summary=_rfa_reason(
                can_satisfy,
                assessment_signal,
                collection_only,
                team.name,
            ),
            created_at=datetime.now(UTC),
            suggested_team_name=team.name if can_satisfy else None,
            candidate_teams=candidates,
        )

    def _team_or_triage(self, candidates: tuple[CandidateTeam, ...]) -> CapabilityTeam:
        if candidates:
            team = self._catalogue.team(candidates[0].team_id)
            if team is not None:
                return team
        return self._catalogue.rfa_teams()[-1]


class CmCapabilityAgent:
    def __init__(self, catalogue: CapabilityCataloguePort) -> None:
        self._catalogue = catalogue

    def review(self, ticket: TicketRecord) -> CmCapabilityReview:
        text = _intake_text(ticket.intake)
        terms = _terms(text)
        clarifications = _base_clarifications(ticket.intake, terms)
        inputs = _recommendation_inputs(ticket)
        candidates = self._catalogue.recommend_cm(
            terms,
            disciplines=inputs.disciplines,
            region=inputs.region,
            priority_tier=inputs.priority_tier,
        )
        team = self._catalogue.team(candidates[0].team_id) if candidates else None
        task_text = " ".join(
            value
            for value in (
                ticket.intake.description,
                ticket.intake.operational_question,
                ticket.intake.required_output_format,
                ticket.intake.customer_success_criteria,
            )
            if value
        )
        collection_hit, collection_negated = _signal_state(task_text, COLLECTION_TERMS)
        signal_present = collection_hit or team is not None
        if collection_hit and team is None:
            team = self._catalogue.default_cm_team()
        can_satisfy = not clarifications and collection_hit
        confidence = _evidence_strength(can_satisfy, signal_present, clarifications)
        _, assessment_negated = _signal_state(text, ASSESSMENT_TERMS)
        risks = _risks(
            ticket.intake,
            terms,
            collection_negated or assessment_negated,
        )
        return CmCapabilityReview(
            review_id=uuid4(),
            ticket_id=ticket.ticket_id,
            can_satisfy=can_satisfy,
            confidence=confidence,
            required_clarifications=clarifications,
            suggested_collection_route=team.team_id if can_satisfy and team else None,
            suggested_collection_sources=_collection_sources(terms, team) if can_satisfy else (),
            estimated_effort=_estimated_effort(ticket.intake.priority),
            risks=risks,
            manager_review_required=True,
            reasoning_summary=_cm_reason(
                can_satisfy,
                collection_hit,
                signal_present,
                team.name if team else None,
            ),
            created_at=datetime.now(UTC),
            suggested_collection_team_id=team.team_id if can_satisfy and team else None,
            suggested_collection_team_name=team.name if can_satisfy and team else None,
            candidate_teams=candidates,
        )


def _recommendation_inputs(ticket: TicketRecord) -> RecommendationInputs:
    intake = ticket.intake
    disciplines = frozenset(
        item.strip() for item in (intake.intelligence_disciplines or "").split(",") if item.strip()
    )
    return RecommendationInputs(
        disciplines=disciplines,
        region=intake.area_or_region,
        priority_tier=assessment_or_computed(ticket).tier,
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
        intake.intelligence_disciplines,
        intake.supported_operation,
    )
    return " ".join(value for value in values if value).casefold()


def _terms(text: str) -> frozenset[str]:
    # Fold simple plurals without adding a stemming dependency.
    tokens = set(_TOKEN_PATTERN.findall(text.casefold()))
    tokens.update(token[:-1] for token in tuple(tokens) if token.endswith("s") and len(token) > 3)
    return frozenset(tokens)


def _base_clarifications(intake: IntakeDetails, terms: frozenset[str]) -> tuple[str, ...]:
    clarifications = list(intake.missing_information)
    if terms.intersection(UNSUPPORTED_TERMS):
        clarifications.append("Confirm a supported mock region and practical collection scope.")
    if intake.deadline is None and (intake.priority or "").casefold() == "critical":
        clarifications.append("Provide the deadline for critical priority routing.")
    return tuple(dict.fromkeys(clarifications))


def _evidence_strength(
    can_satisfy: bool, signal_present: bool, clarifications: tuple[str, ...]
) -> float:
    """Compatibility field measuring evidence completeness, not probability."""

    if clarifications:
        return 0.0
    if can_satisfy:
        return 1.0
    if signal_present:
        return 0.5
    return 0.0


def _risks(
    intake: IntakeDetails, terms: frozenset[str], negated_signal: bool = False
) -> tuple[str, ...]:
    risks: list[str] = []
    if terms.intersection(COLLECTION_TERMS) and not intake.deadline:
        risks.append("Collection timing needs manager confirmation.")
    if (intake.restrictions_or_caveats or "").strip():
        risks.append("Requester restrictions require manager review.")
    if negated_signal:
        risks.append("Negated routing language requires manager review.")
    return tuple(risks)


def _signal_state(text: str, signal_terms: frozenset[str]) -> tuple[bool, bool]:
    """Return positive and negated signal presence without treating negation as intent."""

    normalised = _CONTRACTION_PATTERN.sub(" not ", text.casefold())
    normalised = re.sub(r"\bcannot\b", " not ", normalised)
    tokens = _ROUTING_TOKEN_PATTERN.findall(normalised)
    positive = False
    negated = False
    for index, token in enumerate(tokens):
        if not _matches_signal(token, signal_terms):
            continue
        if _near_negation(tokens, index):
            negated = True
        else:
            positive = True
    return positive, negated


def _matches_signal(token: str, signal_terms: frozenset[str]) -> bool:
    if token in signal_terms:
        return True
    return token.endswith("s") and len(token) > 3 and token[:-1] in signal_terms


def _near_negation(tokens: list[str], signal_index: int) -> bool:
    before = _clause_window(tokens, signal_index, -1)
    after = _clause_window(tokens, signal_index, 1)
    if NEGATION_TERMS.intersection((*before, *after)):
        return True
    return (
        signal_index + 2 < len(tokens)
        and tokens[signal_index + 1] == "?"
        and tokens[signal_index + 2] in NEGATION_TERMS
    )


def _clause_window(tokens: list[str], signal_index: int, direction: int) -> tuple[str, ...]:
    words: list[str] = []
    index = signal_index + direction
    while 0 <= index < len(tokens) and len(words) < NEGATION_WINDOW:
        token = tokens[index]
        if token in _CLAUSE_BOUNDARIES:
            break
        words.append(token)
        index += direction
    return tuple(words)


def _rfa_work_packages(intake: IntakeDetails, team_name: str) -> tuple[str, ...]:
    region = intake.area_or_region or "the nominated mock region"
    return (
        f"Validate the requirement and assumptions for {region} with {team_name}.",
        "Draft the assessment approach and evidence gaps.",
        "Prepare analyst assignment notes for Sprint 9.",
    )


def _collection_sources(terms: frozenset[str], team: CapabilityTeam | None) -> tuple[str, ...]:
    sources = list(team.source_labels) if team else ["collection manager coordination"]
    if "imagery" in terms:
        sources.append("mock imagery holdings")
    if "sensor" in terms:
        sources.append("mock sensor reporting")
    return tuple(dict.fromkeys(sources))


def _estimated_effort(priority: str | None) -> str:
    return "1-2 days" if (priority or "").casefold() in {"critical", "high"} else "3-5 days"


def _rfa_reason(
    can_satisfy: bool, assessment_signal: bool, collection_only: bool, team_name: str
) -> str:
    if can_satisfy:
        return f"RFA can satisfy the request through {team_name}."
    if collection_only:
        return "Request is collection-led and should fall back to collection management."
    if assessment_signal:
        return "RFA signal exists but clarifications are required before approval."
    return "No strong assessment signal was found in the intake."


def _cm_reason(
    can_satisfy: bool, collection_hit: bool, signal_present: bool, team_name: str | None
) -> str:
    if can_satisfy:
        team = team_name or "Collection Coordination Triage Cell"
        return f"Collection management can satisfy the request through {team}."
    if collection_hit:
        return "Collection signal exists but clarifications are required before approval."
    if signal_present:
        return "A collection team keyword matched but no confirmed collection signal was found."
    return "No strong collection signal was found in the intake."
