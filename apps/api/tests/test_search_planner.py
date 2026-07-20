import json
from uuid import uuid4

import pytest

from coeus.domain.tickets import IntakeDetails
from coeus.services.search_planner import (
    EMPTY_SEARCH_PLANNER_ADVICE,
    MAX_CONTEXT_BYTES,
    SEARCH_PLANNER_CONTEXT_SCHEMA_VERSION,
    SEARCH_PLANNER_PROMPT_VERSION,
    SearchPlannerAdvice,
    search_planner_prompt,
    validate_search_planner_advice,
)
from coeus.services.search_planner_agent import SearchPlannerAgent
from coeus.services.search_query_controller import control_search_query


def _raw(**overrides: object) -> str:
    payload: dict[str, object] = {
        "query_expansions": ["maritime logistics"],
        "entities": ["Example Entity"],
        "date_interpretations": ["calendar year 2026"],
        "alternative_terminology": ["supply chain"],
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_prompt_contains_only_bounded_intake_and_explicit_authority_boundary() -> None:
    intake = IntakeDetails(
        title="Synthetic request",
        description="A" * 20_000 + "\x00discard",
        known_context="Sensitive context must stay local",
        restrictions_or_caveats="Sensitive restrictions must stay local",
        suggested_acg_context="private-acg-reference",
        missing_information=("priority",),
        confidence=0.75,
    )

    prompt = search_planner_prompt(intake)
    payload = json.loads(prompt.data)

    assert SEARCH_PLANNER_PROMPT_VERSION in prompt.instructions
    assert SEARCH_PLANNER_CONTEXT_SCHEMA_VERSION in prompt.instructions
    assert "no tools, corpus access, result access or authorisation context" in prompt.instructions
    assert "text search hints only, never structured filters" in prompt.instructions
    assert payload["intake"]["title"] == "Synthetic request"
    assert len(payload["intake"]["description"]) <= 1_000
    assert "\x00" not in payload["intake"]["description"]
    assert "missing_information" not in payload["intake"]
    assert "confidence" not in payload["intake"]
    assert "known_context" not in payload["intake"]
    assert "restrictions_or_caveats" not in payload["intake"]
    assert "suggested_acg_context" not in payload["intake"]
    assert len(prompt.data.encode("utf-8")) <= MAX_CONTEXT_BYTES


def test_prompt_fits_a_large_multibyte_value_in_every_intake_field() -> None:
    values = {
        name: "é" * 2_000
        for name in IntakeDetails.__dataclass_fields__
        if name not in {"missing_information", "confidence"}
    }

    prompt = search_planner_prompt(IntakeDetails(**values))

    assert len(prompt.data.encode("utf-8")) <= MAX_CONTEXT_BYTES
    assert json.loads(prompt.data)["intake"]


def test_parser_accepts_exact_bounded_schema() -> None:
    assert validate_search_planner_advice(_raw()) == SearchPlannerAdvice(
        query_expansions=("maritime logistics",),
        entities=("Example Entity",),
        date_interpretations=("calendar year 2026",),
        alternative_terminology=("supply chain",),
    )


def test_strict_validator_distinguishes_valid_empty_advice_from_invalid_output() -> None:
    empty = json.dumps({name: [] for name in SearchPlannerAdvice.__dataclass_fields__})

    assert validate_search_planner_advice(empty) == EMPTY_SEARCH_PLANNER_ADVICE
    with pytest.raises(ValueError, match="not valid unique-key JSON"):
        validate_search_planner_advice("not-json")


@pytest.mark.parametrize(
    "raw",
    (
        "not-json",
        "[]",
        _raw(extra=[]),
        _raw(entities="Example Entity"),
        _raw(query_expansions=["x"] * 9),
        _raw(entities=[3]),
        _raw(date_interpretations=[""]),
        _raw(alternative_terminology=[" padded "]),
        _raw(entities=["x" * 81]),
        _raw(entities=["unsafe\nvalue"]),
        '{"query_expansions":[],"query_expansions":[],"entities":[],"date_interpretations":[],"alternative_terminology":[]}',
    ),
)
def test_strict_parser_rejects_invalid_advice(raw: str) -> None:
    with pytest.raises(ValueError):
        validate_search_planner_advice(raw)


def test_controller_retains_base_and_appends_normalised_unique_hints() -> None:
    base = "Complete deterministic base query"
    advice = SearchPlannerAdvice(
        query_expansions=("  maritime   logistics  ", "MARITIME LOGISTICS"),
        entities=("Example Entity",),
        date_interpretations=("FY\uff12\uff10\uff12\uff16",),
        alternative_terminology=("supply chain", "unsafe\x00hint"),
    )

    controlled = control_search_query(base, advice)

    assert controlled.text.startswith(base)
    assert controlled.text == (
        base
        + "\nQuery expansion: maritime logistics"
        + "\nEntity: Example Entity"
        + "\nDate interpretation (text only): FY2026"
        + "\nAlternative terminology: supply chain"
    )
    assert tuple((hint.kind, hint.value) for hint in controlled.included_hints) == (
        ("expansion", "maritime logistics"),
        ("entity", "Example Entity"),
        ("date-text-hint", "FY2026"),
        ("alternative-term", "supply chain"),
    )
    assert controlled.advice_truncated is False


def test_controller_stops_before_byte_limit_without_truncating_base_or_hint() -> None:
    base = "base"
    advice = SearchPlannerAdvice(query_expansions=("one", "two"))
    first_only_limit = len((base + "\nQuery expansion: one").encode("utf-8"))

    controlled = control_search_query(base, advice, max_total_bytes=first_only_limit)

    assert controlled.text == base + "\nQuery expansion: one"
    assert [hint.value for hint in controlled.included_hints] == ["one"]
    assert controlled.advice_truncated is True
    assert len(controlled.text.encode("utf-8")) <= first_only_limit


def test_controller_rejects_limit_smaller_than_complete_base() -> None:
    with pytest.raises(ValueError, match="complete base query"):
        control_search_query("base", EMPTY_SEARCH_PLANNER_ADVICE, max_total_bytes=3)


def test_controller_does_not_build_an_advice_only_query() -> None:
    controlled = control_search_query(
        "", SearchPlannerAdvice(query_expansions=("unanchored",)), max_total_bytes=100
    )

    assert controlled.text == ""
    assert controlled.included_hints == ()
    assert controlled.advice_truncated is True


def test_planner_failure_returns_empty_versioned_advice() -> None:
    class FailingAdvisory:
        def advise(self, **_kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("synthetic planner failure")

    plan = SearchPlannerAgent(FailingAdvisory()).plan_safely(  # type: ignore[arg-type]
        uuid4(), IntakeDetails(title="Synthetic request")
    )

    assert plan.suggestions == EMPTY_SEARCH_PLANNER_ADVICE
    assert plan.record.items == ()
    assert plan.record.provenance.outcome == "planner_error_fallback"
    assert plan.record.provenance.error_class == "RuntimeError"
