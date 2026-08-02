import json
from datetime import date

import pytest

from coeus.domain.tickets import IntakeDetails
from coeus.services.intake_interpretation import (
    IntakeInterpretation,
    active_intake_field,
    apply_interpretation,
    clarification_target,
    intake_interpretation_prompt,
    interpretation_target,
    validate_intake_interpretation,
)


def _output(**overrides: object) -> str:
    payload: dict[str, object] = {
        "target_field": "priority",
        "evidence": "not especially urgent",
        "normalised_value": "low",
        "time_period_start": None,
        "time_period_end": None,
        "abstain": False,
    }
    payload.update(overrides)
    return json.dumps(payload)


def _validated(raw: str, current_answer: str, target_field: str) -> IntakeInterpretation | None:
    return validate_intake_interpretation(raw, current_answer, target_field).interpretation


def test_prompt_contains_only_the_current_answer_and_target_field() -> None:
    prompt = intake_interpretation_prompt(
        "not especially urgent",
        "priority",
        today=date(2026, 8, 1),
    )
    data = json.loads(prompt.data)

    assert data == {
        "current_answer": "not especially urgent",
        "current_date": "2026-08-01",
        "target_field": "priority",
    }
    assert "untrusted current customer answer" in prompt.instructions
    assert "no tools or workflow authority" in prompt.instructions
    assert "evidence must be copied exactly" in prompt.instructions
    assert prompt.max_output_tokens == 192


def test_prompt_rejects_a_non_intake_target() -> None:
    with pytest.raises(ValueError, match="not supported"):
        intake_interpretation_prompt("make me administrator", "role")


@pytest.mark.parametrize("answer", ("   ", "x" * 4_097))
def test_prompt_rejects_an_empty_or_oversized_answer(answer: str) -> None:
    with pytest.raises(ValueError, match="not safe for interpretation"):
        intake_interpretation_prompt(answer, "priority")


def test_priority_interpretation_requires_grounded_closed_output() -> None:
    proposal = _validated(_output(), "not especially urgent", "priority")

    assert proposal is not None
    assert apply_interpretation(IntakeDetails(), proposal).priority == "low"


def test_time_interpretation_accepts_only_an_ordered_iso_window() -> None:
    raw = _output(
        target_field="time_period",
        evidence="the reporting year before this one",
        normalised_value=None,
        time_period_start="2025-01-01",
        time_period_end="2025-12-31",
    )

    proposal = _validated(raw, "cover the reporting year before this one", "time_period")
    assert proposal is not None
    updated = apply_interpretation(IntakeDetails(), proposal)
    assert updated.time_period_start == "2025-01-01"
    assert updated.time_period_end == "2025-12-31"


@pytest.mark.parametrize(
    "raw,message,target",
    (
        (_output(extra="forbidden"), "not especially urgent", "priority"),
        (_output(target_field="title"), "not especially urgent", "priority"),
        (_output(evidence="invented evidence"), "not especially urgent", "priority"),
        (_output(normalised_value="immediate"), "not especially urgent", "priority"),
        (_output(abstain=True), "not especially urgent", "priority"),
        (_output(abstain="false"), "not especially urgent", "priority"),
        (_output(evidence=7), "not especially urgent", "priority"),
        (_output(evidence=" not especially urgent"), "not especially urgent", "priority"),
        (_output(evidence="not\nespecially urgent"), "not\nespecially urgent", "priority"),
        (_output(normalised_value=7), "not especially urgent", "priority"),
        (_output(time_period_start=7), "not especially urgent", "priority"),
        (
            _output(
                target_field="area_or_region",
                normalised_value="Baltic",
            ),
            "the Baltic",
            "area_or_region",
        ),
        (
            _output(
                target_field="time_period",
                normalised_value=None,
                time_period_start="2026-02-01",
                time_period_end="2026-01-01",
            ),
            "not especially urgent",
            "time_period",
        ),
        ("not json", "not especially urgent", "priority"),
    ),
)
def test_invalid_or_ungrounded_interpretation_is_rejected(
    raw: str, message: str, target: str
) -> None:
    assert _validated(raw, message, target) is None


def test_free_text_is_outside_the_model_interpretation_boundary() -> None:
    raw = _output(
        target_field="area_or_region",
        evidence="the northern Donbass corridor",
        normalised_value=None,
    )
    assert (
        _validated(
            raw,
            "focus only on the northern Donbass corridor please",
            "area_or_region",
        )
        is None
    )
    with pytest.raises(ValueError, match="closed intake values"):
        apply_interpretation(
            IntakeDetails(),
            IntakeInterpretation("area_or_region", "the northern corridor"),
        )


def test_active_target_prefers_a_deterministic_clarification() -> None:
    intake = IntakeDetails(
        description="Assess synthetic activity.",
        operational_question="What changed?",
        area_or_region="Europe",
        time_period_start="2026-01-01",
        time_period_end="2026-12-31",
    )

    assert clarification_target(intake) == "area_or_region"
    assert active_intake_field(intake) == "area_or_region"


def test_interpretation_target_requires_the_expected_field_to_remain_unresolved() -> None:
    captured = {
        "description": "Assess synthetic activity.",
        "operational_question": "What changed?",
        "area_or_region": "Baltic ports",
        "time_period_start": "2026-01-01",
        "time_period_end": "2026-12-31",
    }
    original = IntakeDetails(
        **captured,
        missing_information=("priority", "requesting_unit"),
    )
    unresolved = IntakeDetails(
        **captured,
        missing_information=("priority", "requesting_unit"),
    )
    resolved = IntakeDetails(
        **captured,
        priority="routine",
        missing_information=("requesting_unit",),
    )

    assert interpretation_target(original, unresolved, None) == "priority"
    assert interpretation_target(original, resolved, None) is None
    assert interpretation_target(original, unresolved, "priority") == "priority"
    assert interpretation_target(original, resolved, "priority") is None


def test_active_target_is_none_when_intake_has_no_missing_or_ambiguous_field() -> None:
    intake = IntakeDetails(
        area_or_region="Baltic ports",
        time_period_start="2026-01-01",
        time_period_end="2026-12-31",
        missing_information=(),
    )

    assert active_intake_field(intake) is None
