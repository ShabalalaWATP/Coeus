from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from coeus.services import search_chunking
from coeus.services.document_extraction import ExtractedPage
from coeus.services.search_chunking import document_chunks


def test_document_chunking_overlaps_pages_and_obeys_asset_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    product = SimpleNamespace(product_id=uuid4())
    asset = SimpleNamespace(
        asset_id=uuid4(),
        name="Synthetic report.docx",
        sha256="a" * 64,
    )
    words = " ".join(f"word-{index}" for index in range(1_100))

    chunks = document_chunks(
        cast(Any, product),
        cast(Any, asset),
        (ExtractedPage(1, ""), ExtractedPage(2, words)),
    )
    assert len(chunks) == 2
    assert chunks[0].page_number == 2
    assert "word-780" in chunks[1].content

    monkeypatch.setattr(search_chunking, "MAX_CHUNKS_PER_ASSET", 1)
    limited = document_chunks(
        cast(Any, product),
        cast(Any, asset),
        (ExtractedPage(1, words), ExtractedPage(2, words)),
    )
    assert len(limited) == 1
