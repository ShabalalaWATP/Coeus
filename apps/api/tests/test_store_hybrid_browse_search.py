import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from store_api_helpers import login


def _payload(
    acg_id: str,
    *,
    title: str,
    summary: str,
    product_type: str,
    tags: list[str] | None = None,
) -> dict[str, object]:
    return {
        "title": title,
        "summary": summary,
        "description": "MOCK DATA ONLY synthetic browse-search fixture.",
        "productType": product_type,
        "sourceType": "finished_assessment",
        "ownerTeam": "RFA",
        "areaOrRegion": "Baltic approaches",
        "classificationLevel": 2,
        "releasability": ["MOCK"],
        "handlingCaveats": ["MOCK DATA ONLY"],
        "tags": tags or ["fixture"],
        "semanticLabels": [],
        "acgIds": [acg_id],
        "assets": [
            {
                "name": f"{product_type}.pdf",
                "assetType": "pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 2_048,
                "sha256": "d" * 64,
            }
        ],
    }


async def _create_product(
    client: AsyncClient,
    csrf_token: str,
    acg_id: str,
    **overrides: object,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/store/products",
        headers={"X-CSRF-Token": csrf_token},
        json=_payload(acg_id, **overrides),
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_store_browse_query_uses_hybrid_token_ranking_and_stemming() -> None:
    app = create_app(
        Settings(environment="test", argon2_memory_cost=8_192, persistence_provider="memory")
    )
    acg_id = str(app.state.access_services.repository.list_acgs()[0].acg_id)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        await _create_product(
            client,
            str(session["csrfToken"]),
            acg_id,
            title="Gulf of Finland Vessel Movement Assessment",
            summary="MOCK DATA ONLY maritime movement review for Baltic approaches.",
            product_type="maritime_fixture",
            tags=["vessel"],
        )
        word_order = await client.get(
            "/api/v1/store/products",
            params={"query": "vessel port", "productType": "maritime_fixture"},
        )
        stemmed = await client.get(
            "/api/v1/store/products",
            params={"query": "vessels", "productType": "maritime_fixture"},
        )
        scattered = await client.get(
            "/api/v1/store/products",
            params={"query": "baltic maritime", "productType": "maritime_fixture"},
        )

    assert word_order.status_code == 200
    assert word_order.json()["total"] == 1
    assert word_order.json()["products"][0]["title"].startswith("Gulf of Finland")
    assert any(
        reason.startswith(("lexical-rank:", "vector-similarity:"))
        for reason in word_order.json()["products"][0]["matchReasons"]
    )
    assert stemmed.json()["total"] == 1
    assert scattered.json()["total"] == 1


@pytest.mark.asyncio
async def test_store_browse_query_does_not_match_cross_word_substrings() -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            embedding_provider="gemini_api",
            persistence_provider="memory",
        )
    )
    acg_id = str(app.state.access_services.repository.list_acgs()[0].acg_id)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        await _create_product(
            client,
            str(session["csrfToken"]),
            acg_id,
            title="Synthetic Report Engine Review",
            summary="MOCK DATA ONLY engine activity with no standalone coastal term.",
            product_type="substring_fixture",
            tags=["engine"],
        )
        response = await client.get(
            "/api/v1/store/products",
            params={"query": "port engin", "productType": "substring_fixture"},
        )

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["products"] == []


@pytest.mark.asyncio
async def test_store_browse_facets_and_pagination_use_full_structured_set() -> None:
    app = create_app(
        Settings(environment="test", argon2_memory_cost=8_192, persistence_provider="memory")
    )
    acg_id = str(app.state.access_services.repository.list_acgs()[0].acg_id)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        for index in range(3):
            await _create_product(
                client,
                str(session["csrfToken"]),
                acg_id,
                title=f"Maritime Fixture {index}",
                summary="MOCK DATA ONLY vessel movement review.",
                product_type="maritime_fixture",
                tags=["fixture-search", "vessel"],
            )
        await _create_product(
            client,
            str(session["csrfToken"]),
            acg_id,
            title="Cyber Fixture",
            summary="MOCK DATA ONLY malware intrusion review.",
            product_type="cyber_fixture",
            tags=["fixture-search", "malware"],
        )
        response = await client.get(
            "/api/v1/store/products",
            params={"query": "vessel movement", "tag": "fixture-search", "page": 2, "pageSize": 2},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["page"] == 2
    assert payload["totalPages"] == 2
    assert len(payload["products"]) == 1
    assert {"maritime_fixture", "cyber_fixture"}.issubset(payload["facets"]["productTypes"])


@pytest.mark.asyncio
async def test_store_browse_applies_structured_filters_and_degrades_to_lexical() -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            embedding_provider="gemini_api",
            persistence_provider="memory",
        )
    )
    acg_id = str(app.state.access_services.repository.list_acgs()[0].acg_id)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        await _create_product(
            client,
            str(session["csrfToken"]),
            acg_id,
            title="Filtered Vessel Fixture",
            summary="MOCK DATA ONLY vessel movement review.",
            product_type="maritime_fixture",
            tags=["vessel"],
        )
        allowed = await client.get(
            "/api/v1/store/products",
            params={"query": "vessel", "productType": "maritime_fixture"},
        )
        blocked = await client.get(
            "/api/v1/store/products",
            params={"query": "vessel", "productType": "cyber_fixture"},
        )

    assert allowed.status_code == 200
    assert allowed.json()["total"] == 1
    assert "retrieval:lexical-only" in allowed.json()["products"][0]["matchReasons"]
    assert blocked.json()["total"] == 0


@pytest.mark.asyncio
async def test_store_browse_gibberish_query_returns_no_mock_embedding_hits() -> None:
    app = create_app(
        Settings(environment="test", argon2_memory_cost=8_192, persistence_provider="memory")
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "admin@example.test")
        response = await client.get("/api/v1/store/products", params={"query": "zzzz"})

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["products"] == []
