from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

SEARCH_EMBEDDING_DIMENSIONS = 1536


@dataclass(frozen=True)
class SearchChunk:
    chunk_id: UUID
    product_id: UUID
    asset_id: UUID | None
    asset_name: str
    asset_sha256: str | None
    page_number: int
    chunk_index: int
    content: str
    content_hash: str
    extractor_version: str
    chunker_version: str


@dataclass(frozen=True)
class SearchChunkEmbedding:
    chunk_id: UUID
    source_hash: str
    vector: tuple[float, ...]


@dataclass(frozen=True)
class SearchTicketDocument:
    ticket_id: UUID
    state: str
    content: str
    content_hash: str


@dataclass(frozen=True)
class SearchTicketEmbedding:
    ticket_id: UUID
    source_hash: str
    vector: tuple[float, ...]


@dataclass(frozen=True)
class SearchTicketHit:
    ticket_id: UUID
    lexical_rank: int | None
    vector_rank: int | None
    lexical_score: float
    vector_score: float


@dataclass(frozen=True)
class SearchAssetIndexState:
    profile_id: UUID
    product_id: UUID
    asset_id: UUID
    asset_sha256: str
    status: str
    page_count: int
    chunk_count: int
    error_code: str | None = None


@dataclass(frozen=True)
class SearchIndexProfile:
    profile_id: UUID
    provider: str
    model: str
    dimensions: int
    generation: int
    space_id: str
    status: str
    is_active: bool
    corpus_version: str
    product_count: int
    chunk_count: int
    indexed_count: int
    failed_count: int
    created_by_user_id: UUID
    created_at: datetime
    completed_at: datetime | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class SearchPassage:
    product_id: UUID
    chunk_id: UUID
    asset_id: UUID | None
    asset_name: str
    page_number: int
    excerpt: str
    lexical_score: float
    vector_score: float
    lexical_rank: int | None
    vector_rank: int | None


@dataclass(frozen=True)
class GroundedProductEvidence:
    product_id: UUID
    passages: tuple[SearchPassage, ...]
    lexical_rank: int | None
    vector_rank: int | None
    lexical_score: float
    vector_score: float


@dataclass(frozen=True)
class GroundedSearchResult:
    evidence: tuple[GroundedProductEvidence, ...]
    retrieval_mode: str
    degraded_reason: str | None
    profile_space_id: str | None
    coverage_status: str = "unknown"
    corpus_version: str | None = None
