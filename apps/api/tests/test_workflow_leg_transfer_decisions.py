"""Decision routing for a proposed cross-team workflow-leg transfer."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from coeus.domain.workflow_leg_transfers import (
    WorkflowLegTransferCommand,
    WorkflowLegTransferConflict,
    WorkflowLegTransferDenied,
    WorkflowLegTransferState,
)
from coeus.persistence.workflow_leg_transfer_decisions import apply_decision, authorise_grants

NOW = datetime(2026, 8, 4, 12, tzinfo=UTC)
SOURCE, TARGET = uuid4(), uuid4()
HASH = "a" * 64


def _command(action: str, **overrides: object) -> WorkflowLegTransferCommand:
    values: dict[str, object] = {
        "command_id": uuid4(),
        "idempotency_key": "key-1",
        "actor_user_id": uuid4(),
        "transfer_id": uuid4(),
        "expected_transfer_version": 1,
        "action": action,
    }
    values.update(overrides)
    return WorkflowLegTransferCommand(**values)  # type: ignore[arg-type]


def _transfer(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "source_unit_id": SOURCE,
        "target_unit_id": TARGET,
        "expires_at": NOW + timedelta(days=1),
        "preview_hash": HASH,
    }
    values.update(overrides)
    return values


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("cancel", WorkflowLegTransferState.CANCELLED),
        ("reject", WorkflowLegTransferState.REJECTED),
        ("expire", WorkflowLegTransferState.EXPIRED),
    ],
)
def test_a_non_accepting_decision_needs_no_database_work(
    action: str, expected: WorkflowLegTransferState
) -> None:
    state, ticket_version, ownership_version = apply_decision(
        object(),  # type: ignore[arg-type]
        _command(action),
        _transfer(),  # type: ignore[arg-type]
        NOW,
        0,
    )

    assert state is expected
    assert ticket_version is None and ownership_version is None


def test_a_lapsed_proposal_expires_whatever_was_asked_for() -> None:
    state, _, _ = apply_decision(
        object(),  # type: ignore[arg-type]
        _command("accept", preview_hash=HASH),
        _transfer(expires_at=NOW),  # type: ignore[arg-type]
        NOW,
        0,
    )

    assert state is WorkflowLegTransferState.EXPIRED


def test_accepting_a_superseded_preview_is_refused() -> None:
    with pytest.raises(WorkflowLegTransferConflict, match="preview is no longer current"):
        apply_decision(
            object(),  # type: ignore[arg-type]
            _command("accept", preview_hash="b" * 64),
            _transfer(),  # type: ignore[arg-type]
            NOW,
            0,
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"target_membership_id": uuid4()},
        {"target_membership_id": uuid4(), "expected_target_membership_version": 1},
        {
            "target_membership_id": uuid4(),
            "expected_target_membership_version": 1,
            "expected_target_account_credential_version": 0,
        },
    ],
)
def test_accepting_without_complete_target_evidence_is_refused(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(WorkflowLegTransferDenied, match="target analyst evidence is required"):
        apply_decision(
            object(),  # type: ignore[arg-type]
            _command("accept", preview_hash=HASH, **overrides),
            _transfer(),  # type: ignore[arg-type]
            NOW,
            0,
        )


def test_a_decision_without_a_transfer_grant_is_refused_before_any_lookup() -> None:
    with pytest.raises(WorkflowLegTransferDenied, match="task transfer authority"):
        authorise_grants(
            object(),  # type: ignore[arg-type]
            _command("reject"),
            _transfer(),  # type: ignore[arg-type]
            NOW,
        )
    with pytest.raises(WorkflowLegTransferDenied, match="task transfer authority"):
        authorise_grants(
            object(),  # type: ignore[arg-type]
            _command("reject", grant_id=uuid4()),
            _transfer(),  # type: ignore[arg-type]
            NOW,
        )
