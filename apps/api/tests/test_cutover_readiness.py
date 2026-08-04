"""Fail-closed unit and HTTP tests for cutover readiness."""

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.api.organisation_dependencies import get_cutover_readiness
from coeus.core.config import Settings
from coeus.domain.cutover_readiness import (
    CutoverCheckCode,
    CutoverCheckStatus,
    CutoverReadinessCheck,
)
from coeus.main import create_app
from coeus.services.cutover_readiness import CutoverReadinessService
from rfi_search_helpers import login


class _Store:
    def __init__(self, checks=None, *, failure: bool = False):  # type: ignore[no-untyped-def]
        self.checks = checks
        self.failure = failure

    def inspect(self):  # type: ignore[no-untyped-def]
        if self.failure:
            raise RuntimeError("database detail must not escape")
        return self.checks


def _database_checks() -> tuple[CutoverReadinessCheck, ...]:
    exact = {
        CutoverCheckCode.MIGRATION_HEAD: 1,
        CutoverCheckCode.IDENTITY_PROJECTION: 1,
        CutoverCheckCode.ROUTING_LEAF_COVERAGE: 7,
        CutoverCheckCode.ROUTING_CAPABILITY_MAPPINGS: 40,
        CutoverCheckCode.JIOC_SERVICE_GRANT: 1,
    }
    return tuple(
        CutoverReadinessCheck(
            code, CutoverCheckStatus.PASSED, exact.get(code, 0), exact.get(code, 0)
        )
        for code in tuple(CutoverCheckCode)[:11]
    )


def test_report_keeps_external_evidence_blocking_and_fails_closed() -> None:
    report = CutoverReadinessService(_Store(_database_checks())).report()
    assert not report.ready
    assert len(report.checks) == 15
    assert all(item.status is CutoverCheckStatus.BLOCKED for item in report.checks[11:])

    failed = CutoverReadinessService(_Store(failure=True)).report()
    assert all(item.status is CutoverCheckStatus.ERROR for item in failed.checks[:11])
    incomplete = CutoverReadinessService(_Store(())).report()
    assert all(item.status is CutoverCheckStatus.ERROR for item in incomplete.checks[:11])


def test_readiness_counts_reject_invalid_values() -> None:
    with pytest.raises(ValueError, match="negative"):
        CutoverReadinessCheck(CutoverCheckCode.MIGRATION_HEAD, CutoverCheckStatus.BLOCKED, -1, 1)


@pytest.mark.asyncio
async def test_cutover_readiness_is_admin_only_and_returns_allowlisted_evidence() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    app.dependency_overrides[get_cutover_readiness] = lambda: CutoverReadinessService(
        _Store(_database_checks())
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "user@example.test")
        denied = await client.get("/api/v1/admin/organisation/cutover-readiness")
        assert denied.status_code == 403
        await login(client, "admin@example.test")
        response = await client.get("/api/v1/admin/organisation/cutover-readiness")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert set(payload["checks"][0]) == {"code", "status", "observedCount", "requiredCount"}
    assert {item["code"] for item in payload["checks"]} == {item.value for item in CutoverCheckCode}
