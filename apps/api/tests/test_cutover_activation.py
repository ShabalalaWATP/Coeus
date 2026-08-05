"""Exact-candidate and separation-of-duties cutover evidence."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from coeus.api.cutover_activation_contracts import call_cutover, release_state
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.cutover_activation import (
    CutoverApprovalRole,
    CutoverExecutionResult,
    CutoverManifest,
    CutoverReleaseState,
    CutoverSlice,
    CutoverSliceApproval,
    CutoverSlicePreview,
    CutoverSliceState,
    CutoverSliceStatus,
)
from coeus.domain.jioc_routing import ROUTING_RELATIONAL_CAPACITY_RELEASE
from coeus.services.cutover_activation import (
    CutoverActivationConflict,
    CutoverActivationDenied,
    CutoverActivationService,
)

NOW = datetime(2026, 8, 4, 9, tzinfo=UTC)
DIGEST = "a" * 64


def _manifest() -> CutoverManifest:
    return CutoverManifest(
        "abcdef123456",
        "20260804_0045",
        "1" * 64,
        "2" * 64,
        "3" * 64,
        ROUTING_RELATIONAL_CAPACITY_RELEASE,
        "4" * 64,
        "ci-1234",
        "5" * 64,
        "6" * 64,
        "security-review-1234",
        "7" * 64,
        "8" * 64,
    )


def _actor(*, active: bool = True, administrator: bool = True) -> UserAccount:
    return UserAccount(
        uuid4(),
        "cutover@example.test",
        "Cutover Operator",
        frozenset({RoleName.ADMINISTRATOR} if administrator else {RoleName.USER}),
        frozenset({Permission.SYSTEM_CONFIGURE} if administrator else ()),
        "hash",
        active,
        3,
    )


class _Store:
    fail: Exception | None = None

    def state(self) -> CutoverReleaseState:
        return CutoverReleaseState(
            None,
            None,
            tuple(
                CutoverSliceState(item, CutoverSliceStatus.NOT_PREVIEWED) for item in CutoverSlice
            ),
            False,
        )

    def preview(self, slice, manifest, actor_user_id, occurred_at):  # type: ignore[no-untyped-def]
        if self.fail:
            raise self.fail
        return CutoverSlicePreview(
            slice,
            manifest.candidate_hash,
            DIGEST,
            actor_user_id,
            occurred_at + timedelta(minutes=15),
        )

    def approve(  # type: ignore[no-untyped-def]
        self, slice, candidate_hash, preview_hash, approval_role, actor_user_id, occurred_at
    ):
        if self.fail:
            raise self.fail
        return CutoverSliceApproval(
            uuid4(),
            slice,
            candidate_hash,
            preview_hash,
            approval_role,
            actor_user_id,
            occurred_at,
        )

    def execute(  # type: ignore[no-untyped-def]
        self, slice, candidate_hash, approval_ids, actor_user_id, occurred_at
    ):
        del approval_ids, actor_user_id, occurred_at
        if self.fail:
            raise self.fail
        return CutoverExecutionResult(candidate_hash, slice, CutoverSliceStatus.ACTIVE, False)

    def active_candidate_is_eligible(
        self, candidate_hash: str, source_revision: str, routing_release: str
    ) -> bool:
        return (
            candidate_hash == _manifest().candidate_hash
            and source_revision == _manifest().source_revision
            and routing_release == _manifest().routing_evaluation_release
        )


def test_manifest_digest_is_stable_and_all_evidence_is_bound() -> None:
    manifest = _manifest()
    assert manifest.candidate_hash == _manifest().candidate_hash
    assert (
        manifest.candidate_hash != replace(manifest, calendar_parity_hash="9" * 64).candidate_hash
    )
    for change in (
        {"schema_head": "unsafe head"},
        {"security_review_hash": "A" * 64},
        {"protected_checks_reference": ""},
    ):
        with pytest.raises(ValueError):
            replace(manifest, **change)


def test_sensitive_transitions_require_current_admin_and_reauthentication() -> None:
    service = CutoverActivationService(_Store())
    for actor in (_actor(active=False), _actor(administrator=False)):
        with pytest.raises(CutoverActivationDenied, match="administrator"):
            service.preview(CutoverSlice.ORGANISATION, _manifest(), actor)
    with pytest.raises(CutoverActivationDenied, match="reauthentication"):
        service.approve(
            CutoverSlice.ORGANISATION,
            DIGEST,
            DIGEST,
            CutoverApprovalRole.SECURITY_REVIEW,
            _actor(),
            reauthenticated=False,
        )


def test_store_enforces_independence_and_stale_evidence_maps_safely() -> None:
    store = _Store()
    service = CutoverActivationService(store)
    actor = _actor()
    store.fail = PermissionError("database detail")
    with pytest.raises(CutoverActivationDenied, match="independent"):
        service.approve(
            CutoverSlice.CALENDAR,
            DIGEST,
            DIGEST,
            CutoverApprovalRole.RELEASE_AUTHORITY,
            actor,
            reauthenticated=True,
        )
    store.fail = ValueError("evidence changed")
    with pytest.raises(CutoverActivationConflict, match="evidence changed"):
        service.preview(CutoverSlice.CALENDAR, _manifest(), actor)


def test_execution_requires_both_distinct_approval_records() -> None:
    store = _Store()
    service = CutoverActivationService(store)
    with pytest.raises(CutoverActivationDenied, match="both distinct"):
        service.execute(
            CutoverSlice.TASK_CAPACITY,
            DIGEST,
            (uuid4(), uuid4())[:1],
            _actor(),
            reauthenticated=True,
        )
    result = service.execute(
        CutoverSlice.TASK_CAPACITY,
        DIGEST,
        (uuid4(), uuid4()),
        _actor(),
        reauthenticated=True,
    )
    assert result.status is CutoverSliceStatus.ACTIVE
    store.fail = PermissionError("hidden")
    with pytest.raises(CutoverActivationDenied, match="executor"):
        service.execute(
            CutoverSlice.TASK_CAPACITY,
            DIGEST,
            (uuid4(), uuid4()),
            _actor(),
            reauthenticated=True,
        )
    store.fail = ValueError("changed")
    with pytest.raises(CutoverActivationConflict, match="changed"):
        service.execute(
            CutoverSlice.TASK_CAPACITY,
            DIGEST,
            (uuid4(), uuid4()),
            _actor(),
            reauthenticated=True,
        )
    approval_id = uuid4()
    with pytest.raises(CutoverActivationDenied, match="both distinct"):
        service.execute(
            CutoverSlice.TASK_CAPACITY,
            DIGEST,
            (approval_id, approval_id),
            _actor(),
            reauthenticated=True,
        )


def test_active_composition_fails_closed_to_unconfigured_or_wrong_candidate() -> None:
    service = CutoverActivationService(_Store())
    with pytest.raises(CutoverActivationDenied, match="not configured"):
        service.assert_active_composition_eligible(None, None)
    with pytest.raises(CutoverActivationDenied, match="not eligible"):
        service.assert_active_composition_eligible("f" * 64, _manifest().source_revision)
    with pytest.raises(ValueError, match="candidate hash"):
        service.assert_active_composition_eligible("invalid", _manifest().source_revision)
    service.assert_active_composition_eligible(
        _manifest().candidate_hash, _manifest().source_revision
    )


def test_approval_success_and_contract_error_mapping() -> None:
    service = CutoverActivationService(_Store())
    approval = service.approve(
        CutoverSlice.ORGANISATION,
        DIGEST,
        DIGEST,
        CutoverApprovalRole.SECURITY_REVIEW,
        _actor(),
        reauthenticated=True,
    )
    assert approval.approval_role is CutoverApprovalRole.SECURITY_REVIEW
    for exception, status in (
        (CutoverActivationDenied("denied"), 403),
        (CutoverActivationConflict("changed"), 409),
        (ValueError("invalid"), 422),
    ):
        with pytest.raises(AppError) as raised:
            call_cutover(lambda exception=exception: (_ for _ in ()).throw(exception))
        assert raised.value.status_code == status


def test_release_contract_includes_exact_manifest_and_both_approvals() -> None:
    first = CutoverSliceApproval(
        uuid4(),
        CutoverSlice.ORGANISATION,
        _manifest().candidate_hash,
        DIGEST,
        CutoverApprovalRole.SECURITY_REVIEW,
        uuid4(),
        NOW,
    )
    second = replace(
        first,
        approval_id=uuid4(),
        approval_role=CutoverApprovalRole.RELEASE_AUTHORITY,
        approved_by_user_id=uuid4(),
    )
    state = CutoverReleaseState(
        _manifest().candidate_hash,
        _manifest(),
        (
            CutoverSliceState(
                CutoverSlice.ORGANISATION,
                CutoverSliceStatus.APPROVED,
                DIGEST,
                uuid4(),
                (first, second),
            ),
        ),
        False,
    )
    response = release_state(state).model_dump(by_alias=True, mode="json")
    assert response["manifest"]["schemaHead"] == "20260804_0045"
    assert {item["approvalRole"] for item in response["slices"][0]["approvals"]} == {
        "security_review",
        "release_authority",
    }
