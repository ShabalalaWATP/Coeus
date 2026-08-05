"""Operator evidence required before a draft audience repair may write."""

import pytest

from coeus.persistence.draft_audience_reconciliation import reconcile_draft_audiences

URL = "postgresql+psycopg://coeus:unused@127.0.0.1:5432/unused"


@pytest.mark.parametrize(
    ("operator", "reason"),
    [(None, None), ("operator", None), (None, "Repairing drift.")],
)
def test_applying_a_repair_needs_both_an_operator_and_a_reason(
    operator: str | None, reason: str | None
) -> None:
    with pytest.raises(ValueError, match="requires an operator and reason"):
        reconcile_draft_audiences(URL, apply=True, operator=operator, reason=reason)


@pytest.mark.parametrize(
    ("operator", "reason"),
    [("x" * 201, "Repairing drift."), ("operator", "x" * 1001)],
)
def test_the_recorded_audit_text_is_bounded(operator: str, reason: str) -> None:
    with pytest.raises(ValueError, match="exceeds the bounded audit length"):
        reconcile_draft_audiences(URL, operator=operator, reason=reason)


def test_a_dry_run_needs_no_operator_evidence_before_it_reaches_the_database() -> None:
    # The argument checks pass, so the failure is the unreachable database
    # rather than a refusal to run.
    with pytest.raises(Exception) as error:
        reconcile_draft_audiences(URL)

    assert not isinstance(error.value, ValueError) or "operator" not in str(error.value)
