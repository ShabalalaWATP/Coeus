"""Sorting is a server contract, so it holds across pages rather than per page."""

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from store_api_helpers import login


def _client() -> AsyncClient:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _titles(client: AsyncClient, query: str) -> list[str]:
    response = await client.get(f"/api/v1/store/products?{query}")
    assert response.status_code == 200
    return [product["title"] for product in response.json()["products"]]


@pytest.mark.asyncio
async def test_title_sort_orders_the_whole_catalogue() -> None:
    async with _client() as client:
        await login(client, "admin@example.test")

        titles = await _titles(client, "productType=assessment_report&sort=title")

    assert titles == sorted(titles, key=str.casefold)


@pytest.mark.asyncio
async def test_coverage_sort_returns_newest_coverage_first() -> None:
    async with _client() as client:
        await login(client, "admin@example.test")

        response = await client.get("/api/v1/store/products?ownerTeam=RFA&sort=coverage")

    assert response.status_code == 200
    starts = [
        product["timePeriodStart"]
        for product in response.json()["products"]
        if product["timePeriodStart"] is not None
    ]
    assert starts == sorted(starts, reverse=True)


@pytest.mark.asyncio
async def test_paging_a_sorted_search_never_repeats_or_reorders_products() -> None:
    async with _client() as client:
        await login(client, "admin@example.test")

        first = await client.get(
            "/api/v1/store/products?ownerTeam=RFA&sort=title&page=1&pageSize=1"
        )
        second = await client.get(
            "/api/v1/store/products?ownerTeam=RFA&sort=title&page=2&pageSize=1"
        )

    first_title = first.json()["products"][0]["title"]
    second_title = second.json()["products"][0]["title"]
    assert first_title.casefold() < second_title.casefold()


@pytest.mark.asyncio
async def test_sort_defaults_to_relevance_and_rejects_unknown_orders() -> None:
    async with _client() as client:
        await login(client, "admin@example.test")

        default = await client.get("/api/v1/store/products?ownerTeam=RFA")
        explicit = await client.get("/api/v1/store/products?ownerTeam=RFA&sort=relevance")
        unknown = await client.get("/api/v1/store/products?ownerTeam=RFA&sort=newest")

    assert default.status_code == 200
    assert explicit.json()["products"] == default.json()["products"]
    assert unknown.status_code == 422


@pytest.mark.asyncio
async def test_search_reports_facet_counts_for_the_visible_catalogue() -> None:
    async with _client() as client:
        await login(client, "admin@example.test")

        response = await client.get("/api/v1/store/products?ownerTeam=RFA")

    payload = response.json()
    facets = payload["facets"]
    counts = facets["counts"]["productTypes"]
    assert facets["productTypes"], "expected at least one product type facet"
    # Every listed value is counted, and nothing is counted that is not listed.
    assert set(counts) == set(facets["productTypes"])
    assert all(count >= 1 for count in counts.values())
    # Facets describe the whole access-scoped result set, not just this page.
    assert sum(counts.values()) == payload["total"]
