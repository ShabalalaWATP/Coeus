"""HTTP contract tests for explicit-disposition merge and split commands."""

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.api.organisation_dependencies import get_organisation_administration
from coeus.core.config import Settings
from coeus.domain.organisation_merge import (
    MergeAffectedRecord,
    MergeRecordKind,
    MergeUnitVersion,
    OrganisationMergeImpact,
    OrganisationMergePreview,
    OrganisationMergeResult,
)
from coeus.domain.organisation_split import (
    OrganisationSplitImpact,
    OrganisationSplitPreview,
    OrganisationSplitResult,
)
from coeus.main import create_app
from rfi_search_helpers import login


class _Merge:
    def __init__(self, impact: OrganisationMergeImpact) -> None:
        self.impact = impact
        self.command = None

    def assess(self, request, actor_id):  # type: ignore[no-untyped-def]
        return self.impact

    def preview(self, plan, actor_id):  # type: ignore[no-untyped-def]
        return OrganisationMergePreview(plan, self.impact, "b" * 64)

    def execute(self, command):  # type: ignore[no-untyped-def]
        self.command = command
        return OrganisationMergeResult(
            command.plan.request.successor.unit_id,
            command.plan.request.successor.expected_version + 1,
            tuple(
                MergeUnitVersion(item.unit_id, item.expected_version + 1)
                for item in command.plan.request.sources
            ),
        )


class _Split:
    def __init__(self, impact: OrganisationSplitImpact) -> None:
        self.impact = impact
        self.command = None

    def assess(self, request, actor_id):  # type: ignore[no-untyped-def]
        return self.impact

    def preview(self, plan, actor_id):  # type: ignore[no-untyped-def]
        return OrganisationSplitPreview(plan, self.impact, "d" * 64)

    def execute(self, command):  # type: ignore[no-untyped-def]
        self.command = command
        request = command.plan.request
        return OrganisationSplitResult(
            MergeUnitVersion(request.source.unit_id, request.source.expected_version + 1),
            MergeUnitVersion(request.parent.unit_id, request.parent.expected_version + 1),
            tuple(MergeUnitVersion(item.unit_id, 1) for item in request.successors),
        )


def _app():  # type: ignore[no-untyped-def]
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    merge_record = MergeAffectedRecord(MergeRecordKind.MEMBERSHIP, uuid4(), uuid4(), 2)
    merge_impact = OrganisationMergeImpact((merge_record,), 0, 0, 4, 0, 0, 0, False, "a" * 64)
    split_record = MergeAffectedRecord(MergeRecordKind.MEMBERSHIP, uuid4(), uuid4(), 3)
    split_impact = OrganisationSplitImpact((split_record,), 0, 0, 0, "c" * 64)
    merge, split = _Merge(merge_impact), _Split(split_impact)
    app.dependency_overrides[get_organisation_administration] = lambda: SimpleNamespace(
        merge=merge, split=split
    )
    return app, merge, split


def _merge_request():  # type: ignore[no-untyped-def]
    sources = [(uuid4(), 1), (uuid4(), 2)]
    successor = (uuid4(), 4)
    return {
        "sources": [
            {"unitId": str(unit_id), "expectedVersion": version} for unit_id, version in sources
        ],
        "successor": {
            "unitId": str(successor[0]),
            "expectedVersion": successor[1],
        },
        "authorities": [
            {"unitId": str(unit_id), "grantId": str(uuid4())}
            for unit_id in (*[item[0] for item in sources], successor[0])
        ],
        "reason": "Merge synthetic delivery teams.",
    }


def _split_request():  # type: ignore[no-untyped-def]
    return {
        "source": {"unitId": str(uuid4()), "expectedVersion": 2},
        "parent": {"unitId": str(uuid4()), "expectedVersion": 5},
        "successors": [
            {
                "unitId": str(uuid4()),
                "name": f"{colour} Synthetic Team",
                "shortName": f"{colour} Team",
                "category": "delivery_team",
                "timeZone": "Europe/London",
                "description": "Synthetic split successor.",
            }
            for colour in ("Red", "Blue")
        ],
        "sourceAuthorisingGrantId": str(uuid4()),
        "parentAuthorisingGrantId": str(uuid4()),
        "reason": "Split the synthetic delivery team.",
    }


@pytest.mark.asyncio
async def test_merge_assess_preview_and_execute_contract() -> None:
    app, merge, _ = _app()
    request = _merge_request()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        headers = {"X-CSRF-Token": session["csrfToken"]}
        assessed = await client.post(
            "/api/v1/admin/organisation/merge-assessments", headers=headers, json=request
        )
        assert assessed.status_code == 200
        record = assessed.json()["records"][0]
        plan = {
            "request": request,
            "dispositions": [
                {
                    "kind": record["kind"],
                    "recordId": record["recordId"],
                    "expectedVersion": record["version"],
                    "action": "move",
                    "targetUnitId": request["successor"]["unitId"],
                    "replacementId": str(uuid4()),
                }
            ],
        }
        preview = await client.post(
            "/api/v1/admin/organisation/merge-previews", headers=headers, json=plan
        )
        assert preview.status_code == 200 and preview.json()["previewHash"] == "b" * 64
        result = await client.post(
            "/api/v1/admin/organisation/merge-commands",
            headers=headers,
            json={
                "commandId": str(uuid4()),
                "idempotencyKey": "merge-synthetic-teams",
                "previewHash": preview.json()["previewHash"],
                "plan": plan,
            },
        )
        assert result.status_code == 200
        assert result.json()["successorVersion"] == 5
    actor = app.state.access_services.repository.get_user_by_username("admin@example.test")
    assert actor is not None and merge.command.actor_user_id == actor.user_id


@pytest.mark.asyncio
async def test_split_assess_preview_and_execute_contract() -> None:
    app, _, split = _app()
    request = _split_request()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        headers = {"X-CSRF-Token": session["csrfToken"]}
        assessed = await client.post(
            "/api/v1/admin/organisation/split-assessments", headers=headers, json=request
        )
        assert assessed.status_code == 200
        record = assessed.json()["records"][0]
        first_successor = request["successors"][0]
        plan = {
            "request": request,
            "dispositions": [
                {
                    "kind": record["kind"],
                    "recordId": record["recordId"],
                    "expectedVersion": record["version"],
                    "action": "move",
                    "targetUnitId": first_successor["unitId"],
                    "replacementId": str(uuid4()),
                }
            ],
        }
        preview = await client.post(
            "/api/v1/admin/organisation/split-previews", headers=headers, json=plan
        )
        assert preview.status_code == 200 and preview.json()["previewHash"] == "d" * 64
        result = await client.post(
            "/api/v1/admin/organisation/split-commands",
            headers=headers,
            json={
                "commandId": str(uuid4()),
                "idempotencyKey": "split-synthetic-team",
                "previewHash": preview.json()["previewHash"],
                "plan": plan,
            },
        )
        assert result.status_code == 200
        assert len(result.json()["successors"]) == 2
    assert split.command.plan.request.successors[0].unit_id == UUID(
        str(request["successors"][0]["unitId"])
    )
