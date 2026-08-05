"""Focused contracts for accountable-owner handover."""

from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.api.organisation_dependencies import get_work_package_handovers
from coeus.api.work_package_handover_contracts import call_handover
from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.work_package_handovers import (
    HandoverWorkPackageCommand,
    ReservationDisposition,
    ReservationHandover,
    WorkPackageHandoverConflict,
    WorkPackageHandoverDenied,
    WorkPackageHandoverPreview,
    WorkPackageHandoverRequest,
    WorkPackageHandoverResult,
    handover_request_hash,
)
from coeus.main import create_app
from coeus.services.work_package_handovers import WorkPackageHandoverService
from rfi_search_helpers import login


def _request() -> WorkPackageHandoverRequest:
    return WorkPackageHandoverRequest(
        uuid4(),
        uuid4(),
        uuid4(),
        2,
        3,
        uuid4(),
        4,
        uuid4(),
        5,
        6,
        "a" * 64,
        8,
        "b" * 64,
        (
            ReservationHandover(
                uuid4(), 1, ReservationDisposition.REPLACE, uuid4(), "replacement-key"
            ),
        ),
    )


def test_handover_hash_binds_actor_and_reservation_disposition() -> None:
    request = _request()
    actor = uuid4()

    assert handover_request_hash(actor, request) != handover_request_hash(uuid4(), request)
    assert handover_request_hash(actor, request) != handover_request_hash(
        actor,
        replace(
            request,
            reservations=(
                replace(
                    request.reservations[0],
                    disposition=ReservationDisposition.RELEASE,
                    replacement_reservation_id=None,
                    replacement_idempotency_key=None,
                ),
            ),
        ),
    )


def test_handover_rejects_partial_replacement_and_duplicate_inventory() -> None:
    with pytest.raises(ValueError, match="replacement reservation identity"):
        ReservationHandover(uuid4(), 1, ReservationDisposition.REPLACE, None, "replacement-key")
    item = ReservationHandover(uuid4(), 1, ReservationDisposition.RELEASE)
    with pytest.raises(ValueError, match="must be unique"):
        replace(_request(), reservations=(item, item))


def test_handover_command_rejects_invalid_evidence() -> None:
    with pytest.raises(ValueError, match="idempotency"):
        HandoverWorkPackageCommand(uuid4(), "", uuid4(), _request(), "a" * 64)
    with pytest.raises(ValueError, match="preview"):
        HandoverWorkPackageCommand(uuid4(), "handover", uuid4(), _request(), "short")


class _Store:
    def __init__(self) -> None:
        self.actor_id: UUID | None = None

    def preview(
        self, actor_user_id: UUID, request: WorkPackageHandoverRequest
    ) -> WorkPackageHandoverPreview:
        self.actor_id = actor_user_id
        return WorkPackageHandoverPreview(
            "a" * 64,
            request.package_id,
            uuid4(),
            request.target_user_id,
            request.expected_package_version,
            request.expected_package_version + 1,
            1,
            1,
            0,
        )

    def execute(self, command: HandoverWorkPackageCommand) -> WorkPackageHandoverResult:
        return WorkPackageHandoverResult(
            command.request.package_id,
            uuid4(),
            command.request.target_user_id,
            command.request.expected_package_version + 1,
            1,
            1,
            False,
        )


def _payload(request: WorkPackageHandoverRequest) -> dict[str, object]:
    item = request.reservations[0]
    return {
        "targetUserId": str(request.target_user_id),
        "expectedPackageVersion": request.expected_package_version,
        "expectedOwnershipVersion": request.expected_ownership_version,
        "authorisingGrantId": str(request.authorising_grant_id),
        "expectedGrantVersion": request.expected_grant_version,
        "targetMembershipId": str(request.target_membership_id),
        "expectedTargetMembershipVersion": request.expected_target_membership_version,
        "expectedTargetAccountCredentialVersion": (
            request.expected_target_account_credential_version
        ),
        "expectedTargetAccountSourceHash": request.expected_target_account_source_hash,
        "expectedTicketVersion": request.expected_ticket_version,
        "expectedTicketSourceHash": request.expected_ticket_source_hash,
        "reservations": [
            {
                "sourceReservationId": str(item.source_reservation_id),
                "expectedSourceVersion": item.expected_source_version,
                "disposition": item.disposition.value,
                "replacementReservationId": str(item.replacement_reservation_id),
                "replacementIdempotencyKey": item.replacement_idempotency_key,
            }
        ],
    }


@pytest.mark.asyncio
async def test_handover_preview_and_command_http_contract() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    store = _Store()
    app.dependency_overrides[get_work_package_handovers] = lambda: WorkPackageHandoverService(store)
    request = _request()
    path = (
        f"/api/v1/organisation/workspaces/{request.unit_id}/work-packages/"
        f"{request.package_id}/handovers"
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
                "idempotencyKey": "handover",
                "request": _payload(request),
                "previewHash": preview.json()["previewHash"],
            },
        )
    assert preview.status_code == 200 and preview.json()["reservationCount"] == 1
    assert result.status_code == 200 and result.json()["replacementReservationCount"] == 1
    assert store.actor_id is not None


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (WorkPackageHandoverDenied("hidden"), 404, "work_package_not_found"),
        (WorkPackageHandoverConflict("stale"), 409, "work_package_handover_conflict"),
        (ValueError("invalid"), 422, "work_package_handover_invalid"),
    ],
)
def test_handover_http_error_mapping(error: Exception, status: int, code: str) -> None:
    with pytest.raises(AppError) as raised:
        call_handover(lambda: (_ for _ in ()).throw(error))
    assert (raised.value.status_code, raised.value.code) == (status, code)
