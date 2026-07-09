from types import SimpleNamespace

import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from coeus.api.routes.auth import client_ip
from coeus.core.config import Settings
from coeus.domain.access import ProductStatus
from coeus.domain.store import StoreProductMetadata
from coeus.main import create_app
from coeus.persistence.store_projection_search import SEARCH_PRODUCTS_SQL, _escape_like
from coeus.repositories.tickets import _max_reference_counter
from coeus.services.store_search_dates import within_dates
from rfi_search_helpers import login, product_payload


def _settings(**overrides) -> Settings:
    return Settings(environment="test", argon2_memory_cost=8_192, **overrides)


def _request(headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": headers or [],
            "client": ("203.0.113.7", 40_000),
        }
    )


def test_client_ip_ignores_forwarded_header_by_default() -> None:
    request = _request([(b"x-forwarded-for", b"198.51.100.9, 192.0.2.1")])

    assert client_ip(request, _settings()) == "203.0.113.7"


def test_client_ip_uses_rightmost_untrusted_hop_when_proxies_are_trusted() -> None:
    settings = _settings(trusted_proxy_count=1)
    request = _request([(b"x-forwarded-for", b"198.51.100.9, 192.0.2.1")])

    assert client_ip(request, settings) == "192.0.2.1"


def test_client_ip_falls_back_when_header_is_missing_or_short() -> None:
    settings = _settings(trusted_proxy_count=2)

    assert client_ip(_request(), settings) == "203.0.113.7"
    short_header = _request([(b"x-forwarded-for", b"192.0.2.1")])
    assert client_ip(short_header, settings) == "203.0.113.7"


def test_removed_gemma_providers_are_rejected() -> None:
    with pytest.raises(ValidationError, match="gemma"):
        _settings(llm_provider="gemma_vertex")
    with pytest.raises(ValidationError, match="gemma"):
        _settings(llm_provider="gemma_vllm")
    assert _settings(llm_provider="gemini_api").llm_provider == "gemini_api"


def test_escape_like_neutralises_wildcards() -> None:
    assert _escape_like(None) is None
    assert _escape_like("100% baltic_ports\\x") == "100\\% baltic\\_ports\\\\x"
    assert "ESCAPE" in SEARCH_PRODUCTS_SQL


def _metadata(start: str | None, end: str | None) -> StoreProductMetadata:
    return StoreProductMetadata(
        title="Test",
        summary="Test",
        description="Test",
        product_type="assessment_report",
        source_type="finished_assessment",
        owner_team="RFA",
        area_or_region="Baltic ports",
        classification_level=1,
        releasability=frozenset({"MOCK"}),
        handling_caveats=frozenset({"MOCK DATA ONLY"}),
        tags=frozenset(),
        acg_ids=frozenset(),
        status=ProductStatus.PUBLISHED,
        time_period_start=start,
        time_period_end=end,
        geojson_ref=None,
        bounding_box=None,
    )


def test_within_dates_parses_dates_and_skips_invalid_values() -> None:
    metadata = _metadata("2026-03-01", "2026-04-30")

    assert within_dates(metadata, None, None) is True
    assert within_dates(metadata, "2026-04-01", None) is True
    assert within_dates(metadata, "2026-05-01", None) is False
    # Invalid filter values are ignored instead of compared lexicographically.
    assert within_dates(metadata, "next week", None) is True
    # Products with unparsable periods are skipped by date filters.
    assert within_dates(_metadata("next week", None), "2026-01-01", None) is False
    assert within_dates(_metadata(None, None), "2026-01-01", None) is False


def test_ticket_reference_counter_restores_from_max_suffix() -> None:
    tickets = (
        SimpleNamespace(reference="TCK-0002"),
        SimpleNamespace(reference="TCK-0009"),
        SimpleNamespace(reference="not-a-reference"),
    )

    assert _max_reference_counter(tickets) == 9  # type: ignore[arg-type]
    assert _max_reference_counter(()) == 0


def test_store_reference_allocation_skips_existing_references() -> None:
    app = create_app(_settings())
    repository = app.state.store_services.repository
    # Simulate a regressed counter; seeds already occupy PROD-1001..PROD-1003.
    repository._reference_counter = 1000

    assert repository.next_reference() == "PROD-1004"


@pytest.mark.asyncio
async def test_ticket_reference_allocation_skips_existing_references() -> None:
    app = create_app(_settings())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        created = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={"message": "Need a briefing note for regional Baltic port activity."},
        )
    assert created.status_code == 201
    repository = app.state.ticket_services.tickets._repository
    repository._counter = 0

    assert repository.next_reference() == "TCK-0002"


@pytest.mark.asyncio
async def test_acg_codes_are_unique_and_inactive_acgs_reject_members() -> None:
    app = create_app(_settings())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        admin = await login(client, "admin@example.test")
        csrf = {"X-CSRF-Token": str(admin["csrfToken"])}
        payload = {
            "code": "ACG-HYGIENE-TEST",
            "name": "Hygiene Test",
            "description": "Synthetic test access group.",
        }
        created = await client.post("/api/v1/acgs", headers=csrf, json=payload)
        duplicate = await client.post("/api/v1/acgs", headers=csrf, json=payload)
        acg_id = created.json()["id"]
        deactivated = await client.patch(
            f"/api/v1/acgs/{acg_id}",
            headers=csrf,
            json={"isActive": False},
        )
        users = await client.get("/api/v1/admin/users")
        target = next(
            item for item in users.json()["users"] if item["username"] == "user@example.test"
        )
        rejected_member = await client.post(
            f"/api/v1/acgs/{acg_id}/members",
            headers=csrf,
            json={"userId": target["id"]},
        )

    assert created.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "acg_code_exists"
    assert deactivated.status_code == 200
    assert rejected_member.status_code == 409
    assert rejected_member.json()["error"]["code"] == "acg_inactive"


@pytest.mark.asyncio
async def test_store_product_time_periods_must_be_iso_dates() -> None:
    app = create_app(_settings())
    acg_id = str(app.state.access_services.repository.list_acgs()[0].acg_id)
    payload = product_payload(acg_id, title="Dated Product")
    payload["timePeriodStart"] = "next week"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        admin = await login(client, "admin@example.test")
        rejected = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
            json=payload,
        )
        payload["timePeriodStart"] = "2026-05-01"
        payload["timePeriodEnd"] = "2026-05-31"
        accepted = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
            json=payload,
        )

    assert rejected.status_code == 422
    assert accepted.status_code == 201
    assert accepted.json()["timePeriodStart"] == "2026-05-01"


def test_analytics_active_count_excludes_cancelled_and_closed_states() -> None:
    from coeus.domain.enums import TicketState
    from coeus.services.feedback_analytics import _is_active

    assert _is_active(SimpleNamespace(state=TicketState.ANALYST_IN_PROGRESS)) is True  # type: ignore[arg-type]
    assert _is_active(SimpleNamespace(state=TicketState.DISSEMINATION_READY)) is True  # type: ignore[arg-type]
    assert _is_active(SimpleNamespace(state=TicketState.CANCELLED)) is False  # type: ignore[arg-type]
    assert (
        _is_active(SimpleNamespace(state=TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED))  # type: ignore[arg-type]
        is False
    )


@pytest.mark.asyncio
async def test_access_diagnostics_requires_csrf_token() -> None:
    app = create_app(_settings())
    product_id = app.state.access_services.repository.list_products()[0].product_id
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        admin = await login(client, "admin@example.test")
        users = await client.get("/api/v1/admin/users")
        target = next(
            item for item in users.json()["users"] if item["username"] == "user@example.test"
        )
        missing_csrf = await client.post(
            f"/api/v1/store/products/{product_id}/access-diagnostics",
            json={"userId": target["id"]},
        )
        assert admin["user"]["username"] == "admin@example.test"

    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["error"]["code"] == "csrf_failed"
