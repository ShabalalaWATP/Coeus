"""Stateless preconditions protecting an exact cutover activation."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from coeus.domain.cutover_activation import (
    CutoverApprovalRole,
    CutoverManifest,
    CutoverSlice,
)
from coeus.domain.jioc_routing import ROUTING_RELATIONAL_CAPACITY_RELEASE
from coeus.persistence.cutover_activation_guards import (
    approval_bindings,
    manifest_bindings,
    require_execution_people,
    require_manifest_evidence,
)

ORGANISATION, CALENDAR, TASKS = "1" * 64, "2" * 64, "3" * 64
AT = datetime(2026, 8, 4, 9, tzinfo=UTC)


def _manifest(**overrides: object) -> CutoverManifest:
    values: dict[str, object] = {
        "candidate_hash": "a" * 64,
        "source_revision": "abcdef123456",
        "schema_head": "20260804_0045",
        "organisation_parity_hash": ORGANISATION,
        "calendar_parity_hash": CALENDAR,
        "task_capacity_parity_hash": TASKS,
        "routing_evaluation_release": ROUTING_RELATIONAL_CAPACITY_RELEASE,
        "routing_evaluation_hash": "4" * 64,
        "protected_checks_reference": "ci-1234",
        "protected_checks_hash": "5" * 64,
        "browser_evidence_hash": "6" * 64,
        "security_review_reference": "security-review-1234",
        "security_review_hash": "7" * 64,
        "backup_restore_hash": "8" * 64,
    }
    values.update(overrides)
    fields = {key: values[key] for key in values if key != "candidate_hash"}
    return CutoverManifest(**fields)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("slice", "digest"),
    [
        (CutoverSlice.ORGANISATION, ORGANISATION),
        (CutoverSlice.CALENDAR, CALENDAR),
        (CutoverSlice.TASK_CAPACITY, TASKS),
    ],
)
def test_each_slice_is_checked_against_its_own_recorded_digest(
    slice: CutoverSlice, digest: str
) -> None:
    require_manifest_evidence(_manifest(), slice, digest, True)

    with pytest.raises(ValueError, match="does not match the current projection"):
        require_manifest_evidence(_manifest(), slice, "9" * 64, True)


def test_a_projection_without_parity_is_never_activated() -> None:
    with pytest.raises(ValueError, match="does not match the current projection"):
        require_manifest_evidence(_manifest(), CutoverSlice.ORGANISATION, ORGANISATION, False)


def test_an_unapproved_routing_release_blocks_every_slice() -> None:
    manifest = _manifest(routing_evaluation_release="routing:unreviewed")

    with pytest.raises(ValueError, match="does not match the current projection"):
        require_manifest_evidence(manifest, CutoverSlice.ORGANISATION, ORGANISATION, True)


def _approval(role: CutoverApprovalRole, approver: UUID) -> dict[str, object]:
    return {"approval_role": role.value, "approved_by_user_id": approver}


def test_four_distinct_people_may_complete_the_ceremony() -> None:
    reviewer, authority = uuid4(), uuid4()
    approvals = (
        _approval(CutoverApprovalRole.SECURITY_REVIEW, reviewer),
        _approval(CutoverApprovalRole.RELEASE_AUTHORITY, authority),
    )

    require_execution_people(approvals, uuid4(), uuid4())  # type: ignore[arg-type]


def test_both_approval_records_and_both_roles_are_required() -> None:
    reviewer = uuid4()
    single = (_approval(CutoverApprovalRole.SECURITY_REVIEW, reviewer),)
    with pytest.raises(ValueError, match="both exact approval records"):
        require_execution_people(single, uuid4(), uuid4())  # type: ignore[arg-type]

    duplicate_role = (
        _approval(CutoverApprovalRole.SECURITY_REVIEW, reviewer),
        _approval(CutoverApprovalRole.SECURITY_REVIEW, uuid4()),
    )
    with pytest.raises(ValueError, match="both approval roles are required"):
        require_execution_people(duplicate_role, uuid4(), uuid4())  # type: ignore[arg-type]


@pytest.mark.parametrize("clash", ["same_approvers", "executor_approved", "executor_proposed"])
def test_no_one_may_hold_two_roles_in_the_ceremony(clash: str) -> None:
    reviewer, authority, proposer, executor = uuid4(), uuid4(), uuid4(), uuid4()
    if clash == "same_approvers":
        authority = reviewer
    elif clash == "executor_approved":
        executor = reviewer
    else:
        executor = proposer
    approvals = (
        _approval(CutoverApprovalRole.SECURITY_REVIEW, reviewer),
        _approval(CutoverApprovalRole.RELEASE_AUTHORITY, authority),
    )

    with pytest.raises(PermissionError, match="must be distinct"):
        require_execution_people(approvals, proposer, executor)  # type: ignore[arg-type]


def test_bindings_carry_the_candidate_and_every_manifest_field() -> None:
    manifest = _manifest()
    actor = uuid4()

    approval = approval_bindings("a" * 64, CutoverSlice.CALENDAR, AT)
    bindings = manifest_bindings(manifest, actor, AT)

    assert approval == {"candidate": "a" * 64, "slice": "calendar", "at": AT}
    assert bindings["candidate"] == manifest.candidate_hash
    assert bindings["actor"] == actor and bindings["at"] == AT
    assert bindings["security_review_hash"] == "7" * 64
