"""HTTP security and contract evidence for cutover activation."""

from datetime import timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.api.organisation_dependencies import get_cutover_activation
from coeus.core.config import Settings
from coeus.domain.cutover_activation import (
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
from coeus.main import create_app
from coeus.services.cutover_activation import CutoverActivationService
from rfi_search_helpers import login

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


class _Store:
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
        return CutoverExecutionResult(candidate_hash, slice, CutoverSliceStatus.ACTIVE, False)

    def active_candidate_is_eligible(self, *args: object) -> bool:
        del args
        return False


def _manifest_payload() -> dict[str, str]:
    manifest = _manifest()
    return {
        "sourceRevision": manifest.source_revision,
        "schemaHead": manifest.schema_head,
        "organisationParityHash": manifest.organisation_parity_hash,
        "calendarParityHash": manifest.calendar_parity_hash,
        "taskCapacityParityHash": manifest.task_capacity_parity_hash,
        "routingEvaluationRelease": manifest.routing_evaluation_release,
        "routingEvaluationHash": manifest.routing_evaluation_hash,
        "protectedChecksReference": manifest.protected_checks_reference,
        "protectedChecksHash": manifest.protected_checks_hash,
        "browserEvidenceHash": manifest.browser_evidence_hash,
        "securityReviewReference": manifest.security_review_reference,
        "securityReviewHash": manifest.security_review_hash,
        "backupRestoreHash": manifest.backup_restore_hash,
    }


@pytest.mark.asyncio
async def test_cutover_http_is_admin_only_csrf_bound_and_uses_safe_contract() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    app.dependency_overrides[get_cutover_activation] = lambda: CutoverActivationService(_Store())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "user@example.test")
        denied = await client.get("/api/v1/admin/organisation/cutover-release")
        session = await login(client, "admin@example.test")
        state = await client.get("/api/v1/admin/organisation/cutover-release")
        missing_csrf = await client.post(
            "/api/v1/admin/organisation/cutover-release/previews/organisation",
            json=_manifest_payload(),
        )
        preview = await client.post(
            "/api/v1/admin/organisation/cutover-release/previews/organisation",
            headers={"X-CSRF-Token": session["csrfToken"]},
            json=_manifest_payload(),
        )
        approval = await client.post(
            "/api/v1/admin/organisation/cutover-release/approvals",
            headers={"X-CSRF-Token": session["csrfToken"]},
            json={
                "slice": "organisation",
                "candidateDigest": _manifest().candidate_hash,
                "previewDigest": DIGEST,
                "approvalRole": "security_review",
                "currentPassword": "CoeusLocal1!",
            },
        )
        executed = await client.post(
            "/api/v1/admin/organisation/cutover-release/execute/organisation",
            headers={"X-CSRF-Token": session["csrfToken"]},
            json={
                "candidateDigest": _manifest().candidate_hash,
                "approvalIds": [str(uuid4()), str(uuid4())],
                "currentPassword": "CoeusLocal1!",
            },
        )

    assert denied.status_code == 403
    assert state.status_code == 200
    assert [item["status"] for item in state.json()["slices"]] == ["not_previewed"] * 3
    assert missing_csrf.status_code == 403
    assert preview.status_code == 200
    assert preview.json()["candidateDigest"] == _manifest().candidate_hash
    assert approval.status_code == 200
    assert approval.json()["approvalRole"] == "security_review"
    assert executed.status_code == 200
    assert executed.json()["status"] == "active"
