from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import RowMapping

from coeus.api.organisation_dependencies import get_work_package_planning
from coeus.core.config import Settings
from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.domain.work_package_planning import (
    WorkPackagePlanningDenied,
    WorkPackagePlanningPreview,
    WorkPackagePlanningResult,
    WorkPackagePlanRequest,
    planning_hash,
)
from coeus.domain.work_packages import CapacityReservation, CapacityReservationState
from coeus.main import create_app
from coeus.persistence.work_package_planning_postgres import _preview
from rfi_search_helpers import login

NOW = datetime(2026, 8, 4, 8, tzinfo=UTC)


def test_preview_hash_binds_canonical_account_evidence() -> None:
    request, actor = _request(), uuid4()
    package = cast(
        RowMapping,
        {
            "version": 1,
            "ownership_version": 2,
            "accountable_user_id": request.accountable_user_id,
        },
    )
    account = cast(RowMapping, {"credential_version": 0, "source_hash": "a" * 64})
    changed = cast(RowMapping, {"credential_version": 1, "source_hash": "b" * 64})
    assert (
        _preview(actor, request, package, account).preview_hash
        != _preview(actor, request, package, changed).preview_hash
    )


def _request(**changes: object) -> WorkPackagePlanRequest:
    value = WorkPackagePlanRequest(
        uuid4(),
        uuid4(),
        1,
        2,
        uuid4(),
        240,
        180,
        NOW + timedelta(days=1),
        2,
        "Synthetic priority.",
        uuid4(),
        NOW,
        NOW + timedelta(hours=4),
        60,
        uuid4(),
    )
    return replace(value, **changes)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"estimated_minutes": 14}, "estimated effort"),
        ({"remaining_minutes": 300}, "remaining effort"),
        ({"reserved_minutes": 200}, "reserved effort"),
        ({"priority": 6}, "priority"),
        ({"ends_at": NOW + timedelta(days=2)}, "reservation must end"),
    ],
)
def test_plan_request_rejects_unsafe_effort_and_schedule(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _request(**changes)


def test_planning_hash_is_actor_and_payload_bound() -> None:
    request, actor = _request(), uuid4()
    assert planning_hash(actor, request) == planning_hash(actor, request)
    assert planning_hash(uuid4(), request) != planning_hash(actor, request)
    assert planning_hash(actor, replace(request, priority=3)) != planning_hash(actor, request)


class _Planning:
    def __init__(self) -> None:
        self.actor_id = None
        self.request = None
        self.command = None
        self.denied = False

    def preview(self, actor_id, request):  # type: ignore[no-untyped-def]
        if self.denied:
            raise WorkPackagePlanningDenied("Synthetic denial.")
        self.actor_id, self.request = actor_id, request
        return WorkPackagePlanningPreview(
            planning_hash(actor_id, request),
            request.package_id,
            request.expected_package_version,
            request.expected_ownership_version,
            request.accountable_user_id,
            request.expected_package_version + 1,
        )

    def execute(self, command):  # type: ignore[no-untyped-def]
        self.command = command
        request = command.request
        reservation = CapacityReservation(
            request.reservation_id,
            request.accountable_user_id,
            uuid4(),
            WorkflowLeg.RFA,
            request.package_id,
            request.starts_at,
            request.ends_at,
            request.reserved_minutes,
            CapacityReservationState.ACTIVE,
            command.idempotency_key,
            1,
            NOW,
            NOW,
        )
        return WorkPackagePlanningResult(
            request.package_id, request.expected_package_version + 1, reservation, False
        )


def _payload(request: WorkPackagePlanRequest) -> dict[str, object]:
    return {
        "expectedPackageVersion": request.expected_package_version,
        "expectedOwnershipVersion": request.expected_ownership_version,
        "accountableUserId": str(request.accountable_user_id),
        "estimatedMinutes": request.estimated_minutes,
        "remainingMinutes": request.remaining_minutes,
        "dueAt": request.due_at.isoformat(),
        "priority": request.priority,
        "priorityOverrideReason": request.priority_override_reason,
        "reservationId": str(request.reservation_id),
        "startsAt": request.starts_at.isoformat(),
        "endsAt": request.ends_at.isoformat(),
        "reservedMinutes": request.reserved_minutes,
        "authorisingGrantId": str(request.authorising_grant_id),
    }


@pytest.mark.asyncio
async def test_package_planning_preview_and_execute_contract() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    planning = _Planning()
    app.dependency_overrides[get_work_package_planning] = lambda: planning
    request = _request()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        headers = {"X-CSRF-Token": session["csrfToken"]}
        path = (
            f"/api/v1/organisation/workspaces/{request.unit_id}/work-packages/"
            f"{request.package_id}/planning"
        )
        preview = await client.post(f"{path}/previews", headers=headers, json=_payload(request))
        assert preview.status_code == 200
        result = await client.post(
            f"{path}/commands",
            headers=headers,
            json={
                "commandId": str(uuid4()),
                "idempotencyKey": "plan-package-1",
                "request": _payload(request),
                "previewHash": preview.json()["previewHash"],
            },
        )
    assert result.status_code == 200
    assert result.json()["packageVersion"] == 2
    assert result.json()["reservation"]["reservedMinutes"] == 60
    assert planning.command.actor_user_id == planning.actor_id


@pytest.mark.asyncio
async def test_package_planning_denial_is_generic_and_csrf_is_required() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    planning = _Planning()
    planning.denied = True
    app.dependency_overrides[get_work_package_planning] = lambda: planning
    request = _request()
    path = (
        f"/api/v1/organisation/workspaces/{request.unit_id}/work-packages/"
        f"{request.package_id}/planning/previews"
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
    assert denied.json()["error"] == {
        "code": "work_package_not_found",
        "message": "Work package was not found.",
    }
