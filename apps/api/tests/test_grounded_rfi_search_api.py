import json
from io import BytesIO
from pathlib import Path

import pytest
from docx import Document
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import submitted_ticket
from store_api_helpers import login, product_payload


class FailingGroundedSearch:
    def search(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("Persisted results must not rerun retrieval.")


@pytest.mark.asyncio
async def test_rfi_search_returns_answer_only_found_in_docx_with_page_citation(
    tmp_path: Path,
) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    regional_acg = next(
        acg for acg in app.state.access_services.repository.list_acgs() if "ALPHA" in acg.code
    )
    metadata = product_payload(str(regional_acg.acg_id))
    metadata.pop("assets")
    metadata.update(
        {
            "title": "Synthetic document-only archive",
            "summary": "MOCK DATA ONLY. Generic archive entry.",
            "description": "Synthetic document used to verify grounded retrieval.",
            "areaOrRegion": "Test sector",
            "tags": ["archive"],
            "status": "published",
        }
    )
    content = _docx(
        "MOCK DATA ONLY. The Velorum lattice indicates three synthetic convoy movements."
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        admin = await login(client, "admin@example.test")
        uploaded = await client.post(
            "/api/v1/store/products/upload",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
            files={
                "asset": (
                    "velorum-evidence.docx",
                    content,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
                "metadata": (None, json.dumps(metadata), "application/json"),
            },
        )
        reindexed = await client.post(
            "/api/v1/admin/search-embeddings/reindex",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
        )
        user = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(
            client,
            str(user["csrfToken"]),
            title="Velorum lattice convoy movements",
            area_or_region="Test sector",
        )
        result = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )
        app.state.rfi_search_service._grounded = FailingGroundedSearch()
        persisted = await client.get(f"/api/v1/rfi-search/{ticket_id}/results")

    assert uploaded.status_code == 201
    assert reindexed.status_code == 202
    assert result.status_code == 200
    assert result.json()["degradedReason"] == "corpus_changed"
    assert persisted.status_code == 200
    offer = next(
        item
        for item in result.json()["offers"]
        if item["title"] == "Synthetic document-only archive"
    )
    passage = next(
        item for item in offer["passages"] if item["assetName"] == "velorum-evidence.docx"
    )
    assert passage["pageNumber"] == 1
    assert "three synthetic convoy movements" in passage["excerpt"]
    assert passage["citation"] == "velorum-evidence.docx, page 1"
    assert persisted.json()["offers"] == result.json()["offers"]


def _docx(text: str) -> bytes:
    stream = BytesIO()
    document = Document()
    document.add_paragraph(text)
    document.save(stream)
    return stream.getvalue()
