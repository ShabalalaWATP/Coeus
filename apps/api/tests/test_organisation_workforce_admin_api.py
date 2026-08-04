"""HTTP contract tests for single-home membership and transfer commands."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.api.organisation_dependencies import get_organisation_administration
from coeus.core.config import Settings
from coeus.domain.organisation import (
    MembershipRole,
    MembershipState,
    TeamMembership,
)
from coeus.domain.organisation_membership import (
    MembershipCommandDenied,
    MembershipMutationPreview,
    MembershipMutationResult,
    MembershipMutationSnapshot,
)
from coeus.domain.organisation_transfer import (
    PersonnelTransferImpact,
    PersonnelTransferPreview,
    PersonnelTransferResult,
    PersonnelTransferStatus,
)
from coeus.main import create_app
from rfi_search_helpers import login


class _Memberships:
    def __init__(self) -> None:
        self.command = None
        self.denied = False

    def preview(self, request, actor_id):  # type: ignore[no-untyped-def]
        if self.denied:
            raise MembershipCommandDenied("Synthetic roster scope denied.")
        snapshot = MembershipMutationSnapshot(1, 0, 0, "b" * 64)
        return MembershipMutationPreview(request, snapshot, "a" * 64)

    def execute(self, command):  # type: ignore[no-untyped-def]
        self.command = command
        return MembershipMutationResult(command.request.membership_id, 1)


class _Transfers:
    def __init__(self) -> None:
        self.command = None

    def preview(self, request, actor_id):  # type: ignore[no-untyped-def]
        impact = PersonnelTransferImpact(2, 0, 1, 2, "d" * 64)
        return PersonnelTransferPreview(request, impact, "c" * 64)

    def execute(self, command):  # type: ignore[no-untyped-def]
        self.command = command
        return PersonnelTransferResult(
            command.command_id,
            command.request.source_membership_id,
            command.request.target_membership_id,
            PersonnelTransferStatus.PENDING,
            command.request.expected_membership_version,
            0,
        )


class _Repository:
    def __init__(self, membership: TeamMembership) -> None:
        self.membership = membership
        self.query = None

    def list_unit_memberships(self, unit_id, *, include_inactive):  # type: ignore[no-untyped-def]
        self.query = (unit_id, include_inactive)
        return (self.membership,)

    def list_memberships(self, user_id):  # type: ignore[no-untyped-def]
        self.query = user_id
        return (self.membership,)


def _app():  # type: ignore[no-untyped-def]
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    memberships, transfers = _Memberships(), _Transfers()
    now = datetime.now(UTC)
    membership = TeamMembership(
        uuid4(),
        uuid4(),
        uuid4(),
        MembershipRole.MANAGER,
        MembershipState.ACTIVE,
        False,
        now,
        uuid4(),
        "Synthetic membership reason.",
        "test",
    )
    repository = _Repository(membership)
    administration = SimpleNamespace(
        memberships=memberships, repository=repository, transfers=transfers
    )
    app.dependency_overrides[get_organisation_administration] = lambda: administration
    return app, memberships, transfers, repository


def _membership_payload():  # type: ignore[no-untyped-def]
    return {
        "operation": "create",
        "membershipId": str(uuid4()),
        "userId": str(uuid4()),
        "unitId": str(uuid4()),
        "expectedVersion": 0,
        "role": "member",
        "assignmentEligible": True,
        "validFrom": datetime.now(UTC).isoformat(),
        "validUntil": None,
        "authorisingGrantId": str(uuid4()),
        "reason": "Post the synthetic analyst.",
    }


def _transfer_payload():  # type: ignore[no-untyped-def]
    return {
        "sourceMembershipId": str(uuid4()),
        "targetMembershipId": str(uuid4()),
        "userId": str(uuid4()),
        "sourceUnitId": str(uuid4()),
        "targetUnitId": str(uuid4()),
        "expectedMembershipVersion": 2,
        "expectedTargetUnitVersion": 3,
        "targetRole": "member",
        "assignmentEligible": True,
        "effectiveAt": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        "sourceAuthorisingGrantId": str(uuid4()),
        "targetAuthorisingGrantId": str(uuid4()),
        "reason": "Transfer the synthetic analyst at one exact boundary.",
    }


@pytest.mark.asyncio
async def test_membership_preview_and_execute_contract() -> None:
    app, memberships, _, _ = _app()
    request = _membership_payload()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        headers = {"X-CSRF-Token": session["csrfToken"]}
        preview = await client.post(
            "/api/v1/admin/organisation/membership-previews",
            headers=headers,
            json=request,
        )
        assert preview.status_code == 200
        assert preview.json()["snapshot"]["currentMembershipVersion"] == 0
        result = await client.post(
            "/api/v1/admin/organisation/membership-commands",
            headers=headers,
            json={
                "commandId": str(uuid4()),
                "idempotencyKey": "post-synthetic-analyst",
                "previewHash": preview.json()["previewHash"],
                "request": request,
            },
        )
        assert result.status_code == 200 and result.json()["version"] == 1
    actor = app.state.access_services.repository.get_user_by_username("admin@example.test")
    assert actor is not None and memberships.command.actor_user_id == actor.user_id


@pytest.mark.asyncio
async def test_transfer_preview_and_execute_contract() -> None:
    app, _, transfers, _ = _app()
    request = _transfer_payload()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        headers = {"X-CSRF-Token": session["csrfToken"]}
        preview = await client.post(
            "/api/v1/admin/organisation/transfer-previews", headers=headers, json=request
        )
        assert preview.status_code == 200
        assert preview.json()["impact"]["namedWorkItems"] == 2
        result = await client.post(
            "/api/v1/admin/organisation/transfer-commands",
            headers=headers,
            json={
                "commandId": str(uuid4()),
                "idempotencyKey": "transfer-synthetic-analyst",
                "previewHash": preview.json()["previewHash"],
                "request": request,
            },
        )
        assert result.status_code == 200
        assert result.json()["status"] == "pending"
    assert transfers.command.request.target_unit_id == UUID(str(request["targetUnitId"]))


@pytest.mark.asyncio
async def test_workforce_route_maps_scoped_denial_without_leaking_details() -> None:
    app, memberships, _, _ = _app()
    memberships.denied = True
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        response = await client.post(
            "/api/v1/admin/organisation/membership-previews",
            headers={"X-CSRF-Token": session["csrfToken"]},
            json=_membership_payload(),
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "organisation_workforce_denied"


@pytest.mark.asyncio
async def test_lists_a_unit_roster_without_exposing_internal_reason() -> None:
    app, _, _, repository = _app()
    unit_id = repository.membership.unit_id
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "admin@example.test")
        response = await client.get(
            f"/api/v1/admin/organisation/units/{unit_id}/memberships",
            params={"includeInactive": "true"},
        )
    assert response.status_code == 200
    assert response.json()["memberships"][0]["role"] == "manager"
    assert "reason" not in response.json()["memberships"][0]
    assert repository.query == (unit_id, True)


@pytest.mark.asyncio
async def test_lists_membership_history_for_one_user() -> None:
    app, _, _, repository = _app()
    user_id = repository.membership.user_id
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "admin@example.test")
        response = await client.get(f"/api/v1/admin/organisation/users/{user_id}/memberships")
    assert response.status_code == 200
    assert response.json()["memberships"][0]["userId"] == str(user_id)
    assert repository.query == user_id
