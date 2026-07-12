"""The store lists nothing unprompted: searching first is required.

Unfiltered browsing of everything a user's ACGs allow is reserved for
catalogue curators (store:browse_all) and administrators; everyone else
must supply a search term or filter.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from store_api_helpers import login


def _client() -> AsyncClient:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.mark.asyncio
async def test_unfiltered_store_listing_requires_a_search_criterion() -> None:
    async with _client() as client:
        await login(client, "user@example.test")

        unfiltered = await client.get("/api/v1/store/products")
        assert unfiltered.status_code == 422
        assert unfiltered.json()["error"]["code"] == "search_criteria_required"

        # Pagination alone is not a criterion.
        paged = await client.get("/api/v1/store/products?page=2&pageSize=10")
        assert paged.status_code == 422

        # Any real criterion unlocks the search.
        queried = await client.get("/api/v1/store/products?query=Regional")
        assert queried.status_code == 200
        typed = await client.get("/api/v1/store/products?productType=assessment_report")
        assert typed.status_code == 200


@pytest.mark.asyncio
async def test_curators_and_admins_may_browse_without_criteria() -> None:
    async with _client() as client:
        await login(client, "store.manager@example.test")
        curator = await client.get("/api/v1/store/products")
        assert curator.status_code == 200

        await login(client, "admin@example.test")
        admin = await client.get("/api/v1/store/products")
        assert admin.status_code == 200


@pytest.mark.asyncio
async def test_owner_team_scope_counts_as_a_criterion() -> None:
    async with _client() as client:
        await login(client, "rfa.manager@example.test")
        mine = await client.get("/api/v1/store/products?ownerTeam=RFA")
        assert mine.status_code == 200
