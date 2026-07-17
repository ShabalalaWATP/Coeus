from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from coeus.domain.search_index import SearchChunk
from coeus.domain.store import StoreAsset, StoreProduct
from coeus.domain.store_semantics import product_semantic_text
from coeus.services.document_extraction import EXTRACTOR_VERSION, ExtractedPage

CHUNKER_VERSION = "words-900-overlap-120-v1"
CHUNK_WORDS = 900
CHUNK_OVERLAP = 120
MAX_CHUNKS_PER_ASSET = 500


def metadata_chunk(product: StoreProduct) -> SearchChunk:
    content = product_semantic_text(product)[:12_000]
    content_hash = sha256(content.encode()).hexdigest()
    return SearchChunk(
        chunk_id=_chunk_id(product.product_id, None, 0, 0, content_hash),
        product_id=product.product_id,
        asset_id=None,
        asset_name="Product metadata",
        asset_sha256=None,
        page_number=0,
        chunk_index=0,
        content=content,
        content_hash=content_hash,
        extractor_version="metadata-v1",
        chunker_version=CHUNKER_VERSION,
    )


def document_chunks(
    product: StoreProduct,
    asset: StoreAsset,
    pages: tuple[ExtractedPage, ...],
) -> tuple[SearchChunk, ...]:
    chunks: list[SearchChunk] = []
    for page in pages:
        words = page.text.split()
        start = 0
        page_index = 0
        while start < len(words) and len(chunks) < MAX_CHUNKS_PER_ASSET:
            content = " ".join(words[start : start + CHUNK_WORDS])[:12_000]
            if content:
                content_hash = sha256(content.encode()).hexdigest()
                chunks.append(
                    SearchChunk(
                        chunk_id=_chunk_id(
                            product.product_id,
                            asset.asset_id,
                            page.page_number,
                            page_index,
                            content_hash,
                        ),
                        product_id=product.product_id,
                        asset_id=asset.asset_id,
                        asset_name=asset.name,
                        asset_sha256=asset.sha256,
                        page_number=page.page_number,
                        chunk_index=page_index,
                        content=content,
                        content_hash=content_hash,
                        extractor_version=EXTRACTOR_VERSION,
                        chunker_version=CHUNKER_VERSION,
                    )
                )
            if start + CHUNK_WORDS >= len(words):
                break
            start += CHUNK_WORDS - CHUNK_OVERLAP
            page_index += 1
    return tuple(chunks)


def _chunk_id(
    product_id: UUID,
    asset_id: UUID | None,
    page_number: int,
    chunk_index: int,
    content_hash: str,
) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        f"coeus-search:{product_id}:{asset_id}:{page_number}:{chunk_index}:{content_hash}",
    )
