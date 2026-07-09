import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.store import object_key_segment
from coeus.main import create_app
from test_store_edge_api import login, product_payload, sized_asset


def test_object_key_segment_strips_directory_traversal() -> None:
    assert object_key_segment("../../etc/passwd") == "passwd"
    assert object_key_segment("..\\..\\windows\\system32") == "system32"
    assert object_key_segment("report.pdf") == "report.pdf"
    assert object_key_segment("..") == "asset"
    assert object_key_segment("   ") == "asset"


def test_object_key_segment_removes_platform_unsafe_characters() -> None:
    assert object_key_segment("../draft:brief?.pdf") == "draft_brief_.pdf"
    assert object_key_segment("line\nbreak.pdf") == "line_break.pdf"
    assert object_key_segment("../<>") == "asset"
    assert len(object_key_segment(f"{'a' * 240}.pdf")) == 180


@pytest.mark.asyncio
async def test_asset_size_over_the_ceiling_is_rejected_at_the_boundary() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    acg_id = str(app.state.access_services.repository.list_acgs()[0].acg_id)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        response = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={**product_payload(acg_id), "assets": [sized_asset(5_000_000_001)]},
        )

    assert response.status_code == 422
