"""Bounded domain contracts for non-authoritative agent advice."""

import re
from dataclasses import dataclass
from enum import StrEnum

MAX_ADVICE_ITEMS = 32
MAX_ADVICE_DETAIL_CHARS = 320
MAX_ADVICE_REFERENCES = 8
MAX_ADVISORY_PROMPT_CHARS = 16_000
MAX_ADVISORY_INSTRUCTIONS_CHARS = 8_000
MAX_ADVISORY_OUTPUT_TOKENS = 512

_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}$")
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_HASH_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")


class AdvisoryAgentKind(StrEnum):
    INTAKE_PLANNER = "intake_planner"
    SEARCH_PLANNER = "search_planner"
    ROUTING_CRITIC = "routing_critic"


class AdviceItemKind(StrEnum):
    CONTRADICTION = "contradiction"
    AMBIGUITY = "ambiguity"
    FOLLOW_UP_STRATEGY = "follow_up_strategy"
    QUERY_EXPANSION = "query_expansion"
    ENTITY = "entity"
    DATE_INTERPRETATION = "date_interpretation"
    ALTERNATIVE_TERMINOLOGY = "alternative_terminology"
    ROUTE_CHALLENGE = "route_challenge"
    MISSING_EVIDENCE = "missing_evidence"
    REVIEW_QUESTION = "review_question"


_ALLOWED_ITEM_KINDS = {
    AdvisoryAgentKind.INTAKE_PLANNER: frozenset(
        {
            AdviceItemKind.CONTRADICTION,
            AdviceItemKind.AMBIGUITY,
            AdviceItemKind.FOLLOW_UP_STRATEGY,
        }
    ),
    AdvisoryAgentKind.SEARCH_PLANNER: frozenset(
        {
            AdviceItemKind.QUERY_EXPANSION,
            AdviceItemKind.ENTITY,
            AdviceItemKind.DATE_INTERPRETATION,
            AdviceItemKind.ALTERNATIVE_TERMINOLOGY,
        }
    ),
    AdvisoryAgentKind.ROUTING_CRITIC: frozenset(
        {
            AdviceItemKind.ROUTE_CHALLENGE,
            AdviceItemKind.MISSING_EVIDENCE,
            AdviceItemKind.REVIEW_QUESTION,
        }
    ),
}


@dataclass(frozen=True)
class AgentAdviceItem:
    """One normalised suggestion which a deterministic controller may ignore."""

    kind: AdviceItemKind
    code: str
    detail: str
    references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _CODE_PATTERN.fullmatch(self.code):
            raise ValueError("Advice item codes must be bounded lower-case identifiers.")
        if (
            not self.detail
            or self.detail != self.detail.strip()
            or len(self.detail) > MAX_ADVICE_DETAIL_CHARS
            or not self.detail.isprintable()
        ):
            raise ValueError("Advice item detail must be bounded, printable and trimmed.")
        if not isinstance(self.references, tuple) or len(self.references) > MAX_ADVICE_REFERENCES:
            raise ValueError("Advice item references must be a bounded tuple.")
        if any(not _REFERENCE_PATTERN.fullmatch(reference) for reference in self.references):
            raise ValueError("Advice item references must be bounded identifiers.")
        if len(set(self.references)) != len(self.references):
            raise ValueError("Advice item references must be unique.")


@dataclass(frozen=True)
class AgentAdviceProvenance:
    """Safe provider facts that can be copied into an ``AgentRun``."""

    provider_attempted: bool
    provider_succeeded: bool
    outcome: str
    provider: str | None
    model: str | None
    duration_ms: int | None
    fallback_outcome: str
    validation_outcome: str
    prompt_version: str
    policy_version: str
    context_schema_version: str
    input_hash: str | None = None
    output_hash: str | None = None
    input_token_count: int | None = None
    output_token_count: int | None = None
    error_class: str | None = None

    def __post_init__(self) -> None:
        if self.provider_succeeded and not self.provider_attempted:
            raise ValueError("A successful provider must have been attempted.")
        codes = (self.outcome, self.fallback_outcome, self.validation_outcome)
        if any(not _CODE_PATTERN.fullmatch(value) for value in codes):
            raise ValueError("Advice provenance outcomes must be bounded identifiers.")
        versions = (self.prompt_version, self.policy_version, self.context_schema_version)
        if any(not _VERSION_PATTERN.fullmatch(value) for value in versions):
            raise ValueError("Advice provenance release identifiers are invalid.")
        _validate_optional_text(self.provider, self.model, self.error_class)
        _validate_optional_hashes(self.input_hash, self.output_hash)
        if self.duration_ms is not None and not 0 <= self.duration_ms <= 2_147_483_647:
            raise ValueError("Advice provenance duration is invalid.")
        _validate_optional_counts(self.input_token_count, self.output_token_count)


@dataclass(frozen=True)
class AgentAdvice:
    agent: AdvisoryAgentKind
    items: tuple[AgentAdviceItem, ...]
    provenance: AgentAdviceProvenance
    verdict: str | None = None
    shadow_only: bool = False
    context_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        validate_advice_items(self.agent, self.items)
        if self.verdict is not None and not _CODE_PATTERN.fullmatch(self.verdict):
            raise ValueError("Agent advice verdict must be a bounded identifier.")
        if self.agent is AdvisoryAgentKind.ROUTING_CRITIC and not self.shadow_only:
            raise ValueError("The routing critic must always be shadow-only.")
        if self.agent is not AdvisoryAgentKind.ROUTING_CRITIC and self.shadow_only:
            raise ValueError("Only the routing critic can be shadow-only.")
        if len(self.context_references) > MAX_ADVICE_REFERENCES or any(
            not _REFERENCE_PATTERN.fullmatch(reference) for reference in self.context_references
        ):
            raise ValueError("Agent advice context references are invalid.")
        if len(set(self.context_references)) != len(self.context_references):
            raise ValueError("Agent advice context references must be unique.")


def validate_advice_items(agent: AdvisoryAgentKind, items: tuple[AgentAdviceItem, ...]) -> None:
    if not isinstance(items, tuple) or len(items) > MAX_ADVICE_ITEMS:
        raise ValueError("Agent advice items must be a bounded tuple.")
    if any(not isinstance(item, AgentAdviceItem) for item in items):
        raise ValueError("Agent advice contains an invalid item.")
    if any(item.kind not in _ALLOWED_ITEM_KINDS[agent] for item in items):
        raise ValueError("Advice item kind is not permitted for this agent.")
    identities = {(item.kind, item.code) for item in items}
    if len(identities) != len(items):
        raise ValueError("Agent advice must not contain duplicate item identities.")


@dataclass(frozen=True)
class AdvisoryPrompt:
    """Transient provider input plus immutable evaluation release identifiers."""

    data: str
    instructions: str
    prompt_version: str
    policy_version: str
    context_schema_version: str
    max_output_tokens: int = 256

    def __post_init__(self) -> None:
        if not self.data or len(self.data) > MAX_ADVISORY_PROMPT_CHARS:
            raise ValueError("Advisory prompt data is empty or exceeds its bound.")
        if not self.instructions or len(self.instructions) > MAX_ADVISORY_INSTRUCTIONS_CHARS:
            raise ValueError("Advisory instructions are empty or exceed their bound.")
        versions = (
            self.prompt_version,
            self.policy_version,
            self.context_schema_version,
        )
        if any(not _VERSION_PATTERN.fullmatch(version) for version in versions):
            raise ValueError("Advisory release identifiers are invalid.")
        if not 1 <= self.max_output_tokens <= MAX_ADVISORY_OUTPUT_TOKENS:
            raise ValueError("Advisory output token limit is invalid.")


def _validate_optional_text(*values: str | None) -> None:
    for value in values:
        if value is not None and (
            not value or value != value.strip() or len(value) > 128 or not value.isprintable()
        ):
            raise ValueError("Advice provenance text is invalid.")


def _validate_optional_hashes(*values: str | None) -> None:
    if any(value is not None and not _HASH_PATTERN.fullmatch(value) for value in values):
        raise ValueError("Advice provenance hashes are invalid.")


def _validate_optional_counts(*values: int | None) -> None:
    if any(value is not None and not 0 <= value <= 2_147_483_647 for value in values):
        raise ValueError("Advice provenance token count is invalid.")
