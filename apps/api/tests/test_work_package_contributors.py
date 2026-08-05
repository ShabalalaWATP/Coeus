from dataclasses import replace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.api.organisation_dependencies import get_work_package_contributors
from coeus.core.config import Settings
from coeus.domain.work_package_contributors import (
    ContributorChangePreview,
    ContributorChangeRequest,
    ContributorChangeResult,
    ContributorOperation,
    WorkPackageContributorDenied,
    contributor_change_hash,
)
from coeus.main import create_app
from rfi_search_helpers import login


def _request(**changes: object) -> ContributorChangeRequest:
    value = ContributorChangeRequest(
        uuid4(),
        uuid4(),
        uuid4(),
        ContributorOperation.ADD,
        3,
        2,
        uuid4(),
        4,
        uuid4(),
        5,
        7,
        "a" * 64,
    )
    return replace(value, **changes)


def test_contributor_request_and_hash_are_version_and_actor_bound() -> None:
    request, actor = _request(), uuid4()
    assert contributor_change_hash(actor, request) == contributor_change_hash(actor, request)
    assert contributor_change_hash(uuid4(), request) != contributor_change_hash(actor, request)
    assert contributor_change_hash(actor, replace(request, expected_membership_version=6)) != (
        contributor_change_hash(actor, request)
    )
    with pytest.raises(ValueError, match="versions"):
        _request(expected_grant_version=0)
    with pytest.raises(ValueError, match="credential"):
        _request(expected_account_credential_version=-1)
    with pytest.raises(ValueError, match="source hash"):
        _request(expected_account_source_hash="not-a-hash")


class _Contributors:
    def __init__(self) -> None:
        self.actor_id = None
        self.command = None
        self.denied = False

    def preview(self, actor_id, request):  # type: ignore[no-untyped-def]
        if self.denied:
            raise WorkPackageContributorDenied("synthetic denial")
        self.actor_id = actor_id
        return ContributorChangePreview(
            contributor_change_hash(actor_id, request),
            request.package_id,
            request.expected_package_version,
            request.expected_ownership_version,
            request.contributor_user_id,
            False,
            request.expected_package_version + 1,
        )

    def execute(self, command):  # type: ignore[no-untyped-def]
        self.command = command
        request = command.request
        return ContributorChangeResult(
            request.package_id,
            request.expected_package_version + 1,
            request.contributor_user_id,
            True,
            False,
        )


def _payload(request: ContributorChangeRequest) -> dict[str, object]:
    return {
        "contributorUserId": str(request.contributor_user_id),
        "operation": request.operation.value,
        "expectedPackageVersion": request.expected_package_version,
        "expectedOwnershipVersion": request.expected_ownership_version,
        "authorisingGrantId": str(request.authorising_grant_id),
        "expectedGrantVersion": request.expected_grant_version,
        "membershipId": str(request.membership_id),
        "expectedMembershipVersion": request.expected_membership_version,
        "expectedAccountCredentialVersion": request.expected_account_credential_version,
        "expectedAccountSourceHash": request.expected_account_source_hash,
    }


@pytest.mark.asyncio
async def test_contributor_preview_and_command_contract() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    contributors = _Contributors()
    app.dependency_overrides[get_work_package_contributors] = lambda: contributors
    request = _request()
    path = (
        f"/api/v1/organisation/workspaces/{request.unit_id}/work-packages/"
        f"{request.package_id}/contributors"
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        headers = {"X-CSRF-Token": session["csrfToken"]}
        preview = await client.post(f"{path}/previews", headers=headers, json=_payload(request))
        result = await client.post(
            f"{path}/commands",
            headers=headers,
            json={
                "commandId": str(uuid4()),
                "idempotencyKey": "contributor-add-1",
                "request": _payload(request),
                "previewHash": preview.json()["previewHash"],
            },
        )
    assert preview.status_code == 200
    assert preview.json()["plannedPackageVersion"] == 4
    assert result.status_code == 200
    assert result.json()["contributorActive"] is True
    assert contributors.command.actor_user_id == contributors.actor_id


@pytest.mark.asyncio
async def test_contributor_denial_is_generic_and_requires_csrf() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    contributors = _Contributors()
    contributors.denied = True
    app.dependency_overrides[get_work_package_contributors] = lambda: contributors
    request = _request()
    path = (
        f"/api/v1/organisation/workspaces/{request.unit_id}/work-packages/"
        f"{request.package_id}/contributors/previews"
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        no_csrf = await client.post(path, json=_payload(request))
        denied = await client.post(
            path,
            headers={"X-CSRF-Token": session["csrfToken"]},
            json=_payload(request),
        )
    assert no_csrf.status_code == 403
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "work_package_not_found"
