"""The rich local demo dataset populates every queue and the analytics.

Runs in ``environment="local"`` with the demo seed explicitly enabled; every
other suite keeps the minimal deterministic seed (see conftest).
"""

from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from coeus.repositories.demo_catalogue import build_demo_catalogue
from coeus.services.demo_seed import _grant_visibility
from rfi_search_helpers import login


def _app(tmp_path: Path) -> FastAPI:
    return create_app(
        Settings(
            environment="local",
            seed_demo_content=True,
            persistence_provider="memory",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )


def test_should_seed_demo_is_auto_on_for_local_only() -> None:
    # Explicit None overrides the conftest env var so the auto rule is tested.
    assert Settings(environment="local", seed_demo_content=None).should_seed_demo() is True
    assert Settings(environment="test", seed_demo_content=None).should_seed_demo() is False
    assert Settings(environment="local", seed_demo_content=False).should_seed_demo() is False
    assert Settings(environment="test", seed_demo_content=True).should_seed_demo() is True


@pytest.mark.asyncio
async def test_demo_store_catalogue_is_broad_and_visible(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        # Catalogue breadth is checked as the curator (browse-all); the demo
        # customer's visibility is proven through the search path below.
        await login(client, "store.manager@example.test")
        products = await client.get("/api/v1/store/products?pageSize=50")
        await login(client, "user@example.test")
        regions = await client.get("/api/v1/store/products?query=Arctic")

    assert products.status_code == 200
    # Base seed plus the demo catalogue, all visible to the demo customer.
    assert products.json()["total"] >= 30
    items = products.json()["products"]
    titles = {product["title"] for product in items}
    assert any("Ransomware" in title for title in titles)

    # A spread of canonical product types is present.
    product_types = {product["productType"] for product in items}
    assert {
        "assessment_report",
        "intelligence_summary",
        "satellite_imagery_product",
        "geographic_product",
        "database_extract",
        "product_bundle",
    } <= product_types

    # Assets carry type-appropriate preview kinds, and bundles have several.
    preview_kinds = {asset["previewKind"] for product in items for asset in product["assets"]}
    assert {"pdf_metadata", "image", "geojson", "text_metadata"} <= preview_kinds
    assert any(len(product["assets"]) > 1 for product in items)
    # Geospatial products expose a layer reference and every product is tagged.
    assert any(product["geojsonRef"] for product in items)
    assert all(product["tags"] for product in items)

    assert regions.status_code == 200
    assert regions.json()["total"] >= 1


@pytest.mark.asyncio
async def test_demo_tickets_populate_every_queue(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "user@example.test")
        customer = await client.get("/api/v1/tickets")

        await login(client, "jioc.team@example.test")
        jioc = await client.get("/api/v1/routing/jioc/queue")

        await login(client, "rfa.manager@example.test")
        rfa = await client.get("/api/v1/routing/rfa/queue")

        await login(client, "collection.manager@example.test")
        cm = await client.get("/api/v1/routing/cm/queue")

        await login(client, "analyst@example.test")
        analyst = await client.get("/api/v1/analyst/tasks")

        await login(client, "qc.manager@example.test")
        qc = await client.get("/api/v1/qc/queue")

    # Customer sees their own demo tickets across the pipeline.
    assert customer.status_code == 200
    customer_states = {ticket["state"] for ticket in customer.json()["tickets"]}
    assert {"DRAFT_INTAKE", "RFI_MATCH_OFFERED", "COLLECT_CHOICE", "DISSEMINATION_READY"} <= (
        customer_states
    )

    jioc_states = {ticket["state"] for ticket in jioc.json()["tickets"]}
    assert "JIOC_REVIEW" in jioc_states
    assert rfa.json()["tickets"], "RFA manager team queue should have demo tickets"
    assert cm.json()["tickets"], "CM manager team queue should have demo tickets"

    analyst_states = {task["state"] for task in analyst.json()["tasks"]}
    assert {"ANALYST_IN_PROGRESS", "MANAGER_APPROVAL", "QC_REVIEW"} <= analyst_states
    qc_refs = {item["reference"] for item in qc.json()["items"]}
    assert qc_refs, "QC queue should have a safe demo summary under review"


@pytest.mark.asyncio
async def test_demo_delivery_feeds_analytics_and_calendars(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "rfa.manager@example.test")
        analytics = await client.get("/api/v1/analytics/rfa")
        teams = await client.get("/api/v1/teams")
        team_id = next(
            team["id"] for team in teams.json()["teams"] if team["name"] == "RFA Assessment Team"
        )
        availability = await client.get(f"/api/v1/teams/{team_id}/availability?date=2026-07-11")
        calendar = await client.get(
            f"/api/v1/teams/{team_id}/calendar?from=2026-07-01&to=2026-08-31"
        )

    assert analytics.status_code == 200
    # Delivered demo tickets produced feedback and disseminations to report.
    data = analytics.json()
    assert data["productReuse"] or data["metrics"]["feedbackSubmitted"] >= 1
    assert calendar.status_code == 200
    assert len(calendar.json()["entries"]) >= 1
    assert availability.status_code == 200
    assert availability.json()["members"] >= 1


@pytest.mark.asyncio
async def test_demo_seed_is_idempotent(tmp_path: Path) -> None:
    from coeus.services.demo_seed import seed_demo_dataset

    app = _app(tmp_path)
    store = app.state.store_services
    tickets = app.state.ticket_services
    before_products = len(store.repository.list_products())
    before_tickets = len(tickets.tickets.assignment_snapshot())

    # Re-running the seed on the already-seeded app is a no-op: the catalogue
    # marker and existing memberships/tickets short-circuit every step.
    seed_demo_dataset(
        app.state.access_services.repository,
        store,
        app.state.object_storage,
        tickets,
        app.state.team_repository,
    )

    assert len(store.repository.list_products()) == before_products
    assert len(tickets.tickets.assignment_snapshot()) == before_tickets


def test_catalogue_and_visibility_skip_unknown_codes() -> None:
    """Defensive branches: unknown ACG codes and absent users are ignored."""

    class _EmptyAccess:
        def get_user_by_username(self, username: str):
            return _Admin() if username == "admin@example.test" else None

        def list_acgs(self):
            return ()

        def add_membership(self, acg_id, user_id):  # pragma: no cover - never reached
            raise AssertionError("no memberships expected without ACGs")

    class _Admin:
        user_id = __import__("uuid").UUID(int=1)

    catalogue = build_demo_catalogue(_EmptyAccess())
    assert catalogue.products == ()
    assert catalogue.acg_codes == frozenset()
    # No ACGs means no memberships are granted and missing users are skipped.
    _grant_visibility(_EmptyAccess(), frozenset({"ACG-EU-CYBER"}))
